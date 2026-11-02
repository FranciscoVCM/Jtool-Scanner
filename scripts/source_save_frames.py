"""Experimental source SAVE-header frame evidence, without scanner binding.

An ordinary palette-body fragment can be less than half a 32px save sprite.
An independently visible closed, lettered header supplies horizontal frame
centre without trusting that fragment's centroid or a particular font bitmap.
Only one 8px X step is allowed; Y, object class, confidence, observed image
box and input order are preserved. Unknown/extended frames abstain.

This module does not classify new saves, read maps, learn tileset templates,
or change scanner defaults. Callers still own original-frame/grid provenance,
warning regeneration, full workflow qualification and source-based review.
"""
from math import ceil, floor
from dataclasses import replace
from collections import Counter
from jtool_scanner.geometry import Box, round_to_step


def luma(rgb):
    return sum(rgb) / 3


def otsu_threshold(values):
    counts = [0] * 256
    for value in values:
        counts[round(value)] += 1
    total = len(values)
    total_sum = sum(i * count for i, count in enumerate(counts))
    weight = running = 0
    best = -1.0
    threshold = 0
    for value, count in enumerate(counts[:-1]):
        weight += count
        running += value * count
        if weight == 0 or weight == total:
            continue
        score = weight * (total-weight) * (running/weight - (total_sum-running)/(total-weight)) ** 2
        if score > best:
            best, threshold = score, value
    return threshold


def runs(values):
    count = 0
    previous = False
    for value in values:
        count += value and not previous
        previous = value
    return count


def panel_candidates(image, window, predicate, sx, sy):
    for top in range(window.y+1, window.bottom-1):
        active = False
        start = window.x
        spans = []
        for x in range(window.x, window.right):
            marked = predicate(*image.pixel(x, top))
            if marked and not active:
                start = x
            if active and not marked:
                spans.append((start, x))
            active = marked
        # Runs touching either window border cannot establish a full panel.
        for left, right in spans:
            if left <= window.x or right >= window.right:
                continue
            if not 24 <= (right-left)/sx <= 32:
                continue
            for height in range(ceil(6*sy), floor(12*sy)+1):
                if top+height >= window.bottom:
                    continue
                box = Box(left, top, right-left, height)
                points = [(x,y) for y in range(box.y,box.bottom)
                          for x in range(box.x,box.right) if predicate(*image.pixel(x,y))]
                yield box, points


def observe_header_x(frame, detections):
    if frame.extent != frame.room:
        return []
    image = frame.original_snapshot()
    room = frame.room
    sx, sy = room.width / 800, room.height / 608
    rows = []
    for index, detection in enumerate(detections):
        if detection.type_id != 12 or detection.kind != 'save':
            continue
        if detection.image_box.width / sx >= 16:
            continue
        body = detection.image_box
        left = max(room.x, int(body.center_x - 32 * sx))
        right = min(room.right, ceil(body.center_x + 32 * sx))
        top = max(room.y, int(body.y - 24 * sy))
        bottom = min(room.bottom, body.y)
        if right <= left or bottom <= top:
            continue
        window = Box(left, top, right-left, bottom-top)
        values = [luma(image.pixel(x,y)) for y in range(top,bottom) for x in range(left,right)]
        low, high = min(values), max(values)
        if high - low <= 2:
            rows.append(dict(index=index, original=[12,detection.x,detection.y], panels=[], selected=None, reason='no above-quantum contrast'))
            continue
        panels = []
        for polarity in ('low','high'):
            threshold = otsu_threshold(values)
            predicate = (lambda r,g,b: round((r+g+b)/3) <= threshold) if polarity == 'low' else (lambda r,g,b: round((r+g+b)/3) > threshold)
            for box, pixels in panel_candidates(image, window, predicate, sx, sy):
                width, height = box.width/sx, box.height/sy
                if not (24 <= width <= 32 and 6 <= height <= 12):
                    continue
                if box.x <= left or box.y <= top or box.right >= right or box.bottom >= bottom:
                    continue
                points = set(pixels)
                faces = [
                    sum((x,box.y) in points for x in range(box.x,box.right))/box.width,
                    sum((x,box.bottom-1) in points for x in range(box.x,box.right))/box.width,
                    sum((box.x,y) in points for y in range(box.y,box.bottom))/box.height,
                    sum((box.right-1,y) in points for y in range(box.y,box.bottom))/box.height,
                ]
                if min(faces) < .75:
                    continue
                letter_rows = sum(runs([not predicate(*image.pixel(x,y)) for x in range(box.x+1,box.right-1)]) >= 2
                                  for y in range(box.y+1,box.bottom-1))
                if letter_rows < 2:
                    continue
                x = round_to_step((box.center_x-room.x)/sx - 16, 8)
                if abs(x-detection.x) > 8 or not 0 <= x <= 768:
                    continue
                if (body.x < room.x+x*sx or body.right > room.x+(x+32)*sx
                        or (body.y-box.bottom)/sy > 16):
                    continue
                if not frame.rectangle_available(x,detection.y,32,32):
                    continue
                panels.append(dict(x=x,polarity=polarity,box=dict(x=box.x,y=box.y,width=box.width,height=box.height),
                                   faces=faces,letter_rows=letter_rows,native_width=width,native_height=height))
        rows.append(dict(index=index, original=[12,detection.x,detection.y],panels=panels,
                         selected=next(iter({p['x'] for p in panels})) if len({p['x'] for p in panels})==1 else None))
    return rows



def align_source_save_headers(frame, detections):
    """Return position-only replacements and isolated evidence; never mutate input.

    A competing existing save, or two proposed saves sharing a destination,
    makes the correction ambiguous. Preserve those original records instead
    of coalescing markers or silently changing duplicate counts.
    """
    originals = list(detections)
    rows = observe_header_x(frame, originals)
    proposed = {row['index']: row['selected'] for row in rows
                if row['selected'] is not None
                and row['selected'] != originals[row['index']].x}
    destinations = Counter((originals[i].type_id, x, originals[i].y)
                           for i, x in proposed.items())
    output = list(originals)
    changes = []
    for index, x in proposed.items():
        detection = originals[index]
        destination = detection.type_id, x, detection.y
        occupied = any(j != index and other.type_id in (12, 26)
                       and (other.x, other.y) == (x, detection.y)
                       for j, other in enumerate(originals))
        if occupied or destinations[destination] != 1:
            continue
        output[index] = replace(detection, x=x)
        changes.append(dict(index=index, before=[detection.x, detection.y],
                            after=[x, detection.y]))
    return output, dict(rows=rows, changes=changes,
                        no_new_objects=True, input_order_preserved=True,
                        only_existing_save_x_changes=True)
