(() => {
  "use strict";

  const ROOM_WIDTH = 800;
  const ROOM_HEIGHT = 608;
  const MINI_TYPES = new Set([2, 7, 8, 9, 10, 27]);
  const SAVE_TYPES = new Set([12, 26]);
  const WATER_TYPES = new Set([14, 15, 23]);
  const TYPE_GROUPS = [
    ["Terrain", [1, 2, 18, 27, 13]],
    ["Full spikes", [3, 4, 5, 6]],
    ["Mini spikes", [7, 8, 9, 10]],
    ["Movement", [14, 15, 23, 16, 17, 24, 25, 22]],
    ["Objects", [12, 26, 21, 11, 19]],
  ];
  const GLYPHS = {
    1: "■", 2: "▪", 3: "▲", 4: "▶", 5: "◀", 6: "▼",
    7: "▴", 8: "▸", 9: "◂", 10: "▾", 11: "●", 12: "S",
    13: "━", 14: "▧", 15: "▧", 16: "▥", 17: "▥", 18: "▣",
    19: "▬", 20: "K", 21: "◉", 22: "↥", 23: "▧", 24: "⬆",
    25: "⬇", 26: "S", 27: "▫",
  };
  const COLORS = {
    1: "#aeb4b8", 2: "#aeb4b8", 3: "#d7dcdf", 4: "#d7dcdf",
    5: "#d7dcdf", 6: "#d7dcdf", 7: "#eef1f2", 8: "#eef1f2",
    9: "#eef1f2", 10: "#eef1f2", 11: "#cf513c", 12: "#ebe044",
    13: "#969da2", 14: "#5ba9e8", 15: "#7ecfd0", 16: "#2b8738",
    17: "#2b8738", 18: "#b95d61", 19: "#b9c0c4", 20: "#4169e1",
    21: "#7827ff", 22: "#d8d8d8", 23: "#9fe4e4", 24: "#ff6868",
    25: "#55bce8", 26: "#ebe044", 27: "#b95d61",
  };

  const $ = (id) => document.getElementById(id);
  const elements = {};
  const state = {
    metadata: null,
    project: null,
    selectedId: null,
    selectedType: 1,
    tool: "select",
    view: "map",
    zoom: 1,
    undo: [],
    redo: [],
    sourceFile: null,
    sourceUrl: null,
    previewUrl: null,
    previewTimer: null,
    drag: null,
    dirty: false,
  };

  document.addEventListener("DOMContentLoaded", initialize);

  async function initialize() {
    cacheElements();
    bindEvents();
    state.metadata = await apiJson("/api/metadata");
    populateTypeControls();
    renderPalette();
    renderAll();
  }

  function cacheElements() {
    for (const id of [
      "documentName", "newButton", "openButton", "saveProjectButton", "exportButton",
      "mobilePaletteButton", "mobileInspectorButton",
      "fileInput", "emptyOpenButton", "rescanButton", "gridStep",
      "geometryScan", "colorScan", "ocrScan", "paletteSearch", "objectPalette",
      "objectsTab", "scanTab", "inspectorTab", "layersTab",
      "undoButton", "redoButton", "snapSelect", "zoomOut", "zoomIn", "zoomFit",
      "zoomLabel", "stageViewport", "stage", "emptyState", "sourceLayer", "mapLayer",
      "interactionLayer", "statusText", "coordinateText", "objectCount", "noSelection",
      "selectionInspector", "selectedSwatch", "selectedName", "deleteButton",
      "objectTypeSelect", "objectX", "objectY", "objectEnabled", "objectId",
      "objectSource", "objectScore", "duplicateButton", "startHereButton",
      "infiniteJump", "startPolicy", "bulkWater", "applyWaterButton", "layerSearch",
      "confidenceFilter", "layerList", "toastRegion", "busyOverlay", "busyTitle",
    ]) elements[id] = $(id);
  }

  function bindEvents() {
    elements.openButton.addEventListener("click", openFilePicker);
    elements.mobilePaletteButton.addEventListener("click", () => toggleMobilePanel("left"));
    elements.mobileInspectorButton.addEventListener("click", () => toggleMobilePanel("right"));
    elements.emptyOpenButton.addEventListener("click", openFilePicker);
    elements.fileInput.addEventListener("change", onFileChosen);
    elements.newButton.addEventListener("click", newProject);
    elements.rescanButton.addEventListener("click", () => state.sourceFile && scanSource(state.sourceFile));
    elements.saveProjectButton.addEventListener("click", downloadProject);
    elements.exportButton.addEventListener("click", downloadJmap);
    elements.paletteSearch.addEventListener("input", renderPalette);
    elements.layerSearch.addEventListener("input", renderLayers);
    elements.confidenceFilter.addEventListener("change", renderLayers);
    elements.undoButton.addEventListener("click", undo);
    elements.redoButton.addEventListener("click", redo);
    elements.zoomOut.addEventListener("click", () => setZoom(state.zoom - 0.1));
    elements.zoomIn.addEventListener("click", () => setZoom(state.zoom + 0.1));
    elements.zoomFit.addEventListener("click", fitZoom);
    elements.deleteButton.addEventListener("click", disableSelected);
    elements.duplicateButton.addEventListener("click", duplicateSelected);
    elements.startHereButton.addEventListener("click", chooseSelectedStart);
    elements.objectTypeSelect.addEventListener("change", updateSelectedFromInspector);
    elements.objectX.addEventListener("change", updateSelectedFromInspector);
    elements.objectY.addEventListener("change", updateSelectedFromInspector);
    elements.objectEnabled.addEventListener("change", updateSelectedFromInspector);
    elements.infiniteJump.addEventListener("change", updateSettings);
    elements.startPolicy.addEventListener("change", updateStartPolicy);
    elements.applyWaterButton.addEventListener("click", replaceAllWater);
    elements.interactionLayer.addEventListener("pointerdown", onPointerDown);
    elements.interactionLayer.addEventListener("pointermove", onPointerMove);
    elements.interactionLayer.addEventListener("pointerup", onPointerUp);
    elements.interactionLayer.addEventListener("pointercancel", onPointerUp);
    window.addEventListener("resize", () => state.project && fitZoom(false));
    document.addEventListener("keydown", onKeyDown);

    document.querySelectorAll("[data-tool]").forEach((button) => {
      button.addEventListener("click", () => setTool(button.dataset.tool));
    });
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.addEventListener("click", () => setView(button.dataset.view));
    });
    document.querySelectorAll("[data-left-tab]").forEach((button) => {
      button.addEventListener("click", () => setTab("left", button.dataset.leftTab));
    });
    document.querySelectorAll("[data-right-tab]").forEach((button) => {
      button.addEventListener("click", () => setTab("right", button.dataset.rightTab));
    });
  }

  function populateTypeControls() {
    const options = state.metadata.object_types
      .filter((item) => item.id !== 20)
      .map((item) => `<option value="${item.id}">${prettyName(item.name)}</option>`)
      .join("");
    elements.objectTypeSelect.innerHTML = options;
  }

  function renderPalette() {
    if (!state.metadata) return;
    const query = elements.paletteSearch.value.trim().toLowerCase();
    const names = new Map(state.metadata.object_types.map((item) => [item.id, item.name]));
    elements.objectPalette.innerHTML = TYPE_GROUPS.map(([group, ids]) => {
      const buttons = ids
        .filter((id) => !query || prettyName(names.get(id)).toLowerCase().includes(query))
        .map((id) => `
          <button class="palette-item ${state.selectedType === id ? "active" : ""}"
                  data-type-id="${id}" title="${prettyName(names.get(id))}">
            <span class="palette-glyph" style="color:${COLORS[id]}">${GLYPHS[id]}</span>
            <small>${id}</small>
          </button>`).join("");
      return buttons ? `<section class="palette-group"><h3>${group}</h3><div class="palette-grid">${buttons}</div></section>` : "";
    }).join("");
    elements.objectPalette.querySelectorAll("[data-type-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedType = Number(button.dataset.typeId);
        setTool("add");
        renderPalette();
      });
    });
  }

  function blankProject() {
    return {
      format: "jtool-scanner-correction", version: 1,
      source: {
        image: null, image_width: 800, image_height: 608,
        room_box: { x: 0, y: 0, width: 800, height: 608 },
      },
      scanner: {
        grid_step: 8, include_color_objects: true, include_geometry: true,
        source_grid: null, recognized_text: "",
      },
      start: { policy: "auto", save_id: null, position: null },
      jmap: {
        version: "1.3.5", infinite_jump: 0, dot_kid: 0, save_type: 1,
        border_type: 0, player_xscale: 1, player_gravity: 1,
      },
      objects: [], history: [{ operation: "create_in_app" }],
    };
  }

  function newProject() {
    if (state.dirty && !window.confirm("Discard the current unsaved corrections?")) return;
    setProject(blankProject(), "Untitled.jscan.json");
    clearSource();
    toast("New correction project created");
  }

  function openFilePicker() {
    elements.fileInput.value = "";
    elements.fileInput.click();
  }

  async function onFileChosen(event) {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.name.toLowerCase().endsWith(".png")) {
        setSourceFile(file);
        await scanSource(file);
      } else if (file.name.toLowerCase().endsWith(".jmap")) {
        setBusy(true, "Opening JTool map");
        const response = await fetch("/api/import-jmap", {
          method: "POST",
          headers: { "Content-Type": "text/plain", "X-Filename": file.name },
          body: await file.text(),
        });
        const data = await responseJson(response);
        clearSource();
        setProject(data.project, file.name.replace(/\.jmap$/i, ".jscan.json"));
      } else {
        const data = JSON.parse(await file.text());
        if (data.format !== "jtool-scanner-correction") throw new Error("This JSON file is not a correction project.");
        clearSource();
        setProject(data, file.name);
      }
    } catch (error) {
      toast(error.message || String(error), true);
    } finally {
      setBusy(false);
    }
  }

  async function scanSource(file) {
    setBusy(true, "Scanning screen");
    elements.statusText.textContent = "Scanning…";
    try {
      const params = new URLSearchParams({
        grid_step: elements.gridStep.value,
        color: String(elements.colorScan.checked),
        geometry: String(elements.geometryScan.checked),
        ocr: String(elements.ocrScan.checked),
        start_policy: "auto",
      });
      const response = await fetch(`/api/scan?${params}`, {
        method: "POST",
        headers: { "Content-Type": "image/png", "X-Filename": file.name },
        body: file,
      });
      const data = await responseJson(response);
      setProject(data.project, file.name.replace(/\.png$/i, ".jscan.json"));
      drawSourceImage();
      toast(`Scan complete: ${data.project.objects.length} candidates`);
    } catch (error) {
      elements.statusText.textContent = "Scan failed";
      toast(error.message || String(error), true);
    } finally {
      setBusy(false);
    }
  }

  function setProject(project, name) {
    state.project = project;
    state.selectedId = null;
    state.undo = [];
    state.redo = [];
    state.dirty = false;
    elements.documentName.textContent = name || project.source?.image || "Untitled";
    elements.emptyState.classList.add("hidden");
    elements.stage.classList.remove("hidden");
    elements.rescanButton.disabled = !state.sourceFile;
    syncSettings();
    fitZoom(false);
    renderAll();
    schedulePreview(0);
  }

  function setSourceFile(file) {
    clearSource();
    state.sourceFile = file;
    state.sourceUrl = URL.createObjectURL(file);
    elements.rescanButton.disabled = false;
  }

  function clearSource() {
    if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
    state.sourceFile = null;
    state.sourceUrl = null;
    const context = elements.sourceLayer.getContext("2d");
    context.clearRect(0, 0, ROOM_WIDTH, ROOM_HEIGHT);
    elements.rescanButton.disabled = true;
  }

  function drawSourceImage() {
    if (!state.sourceUrl || !state.project) return;
    const image = new Image();
    image.onload = () => {
      const context = elements.sourceLayer.getContext("2d");
      context.clearRect(0, 0, ROOM_WIDTH, ROOM_HEIGHT);
      const room = state.project.source.room_box;
      const grid = state.project.scanner.source_grid;
      let target = { x: 0, y: 0, width: ROOM_WIDTH, height: ROOM_HEIGHT };
      if (grid && (grid[0] !== 25 || grid[1] !== 19)) {
        const columns = Math.min(25, grid[0]);
        const rows = Math.min(19, grid[1]);
        const width = columns * 32;
        const height = rows * 32;
        target = {
          x: Math.floor((25 - columns) / 2) * 32,
          y: Math.ceil((19 - rows) / 2) * 32,
          width,
          height,
        };
      }
      context.drawImage(image, room.x, room.y, room.width, room.height,
        target.x, target.y, target.width, target.height);
    };
    image.src = state.sourceUrl;
  }

  function renderAll() {
    const hasProject = Boolean(state.project);
    elements.saveProjectButton.disabled = !hasProject;
    elements.exportButton.disabled = !hasProject;
    elements.undoButton.disabled = !state.undo.length;
    elements.redoButton.disabled = !state.redo.length;
    if (!hasProject) return;
    renderOverlay();
    renderInspector();
    renderLayers();
    renderCounts();
  }

  function renderOverlay() {
    const canvas = elements.interactionLayer;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, ROOM_WIDTH, ROOM_HEIGHT);
    for (const object of state.project.objects) {
      if (object.enabled) continue;
      const size = objectSize(object.type_id);
      context.save();
      context.strokeStyle = "#d12b2b";
      context.lineWidth = 2;
      context.setLineDash([5, 3]);
      context.strokeRect(object.x + 1, object.y + 1, size - 2, size - 2);
      context.restore();
    }
    const selected = selectedObject();
    if (selected) {
      const size = objectSize(selected.type_id);
      context.save();
      context.strokeStyle = "#00a870";
      context.fillStyle = "rgba(0,168,112,.12)";
      context.lineWidth = 3;
      context.fillRect(selected.x, selected.y, size, size);
      context.strokeRect(selected.x - 1.5, selected.y - 1.5, size + 3, size + 3);
      context.fillStyle = "#fff";
      context.strokeStyle = "#006b4a";
      for (const [x, y] of [[selected.x, selected.y], [selected.x + size, selected.y + size]]) {
        context.fillRect(x - 3, y - 3, 6, 6);
        context.strokeRect(x - 3, y - 3, 6, 6);
      }
      context.restore();
    }
  }

  function renderInspector() {
    const object = selectedObject();
    elements.noSelection.classList.toggle("hidden", Boolean(object));
    elements.selectionInspector.classList.toggle("hidden", !object);
    if (!object) return;
    const name = typeName(object.type_id);
    elements.selectedName.textContent = prettyName(name);
    elements.selectedSwatch.style.background = COLORS[object.type_id] || "#bbb";
    elements.objectTypeSelect.value = String(object.type_id);
    elements.objectX.value = object.x;
    elements.objectY.value = object.y;
    elements.objectEnabled.checked = object.enabled;
    elements.objectId.textContent = object.id;
    elements.objectSource.textContent = object.detection_kind || object.source;
    elements.objectScore.textContent = object.score == null ? "Manual" : `${Math.round(object.score * 100)}%`;
    elements.startHereButton.classList.toggle("hidden", !SAVE_TYPES.has(object.type_id));
    elements.startHereButton.textContent =
      state.project.start.save_id === object.id ? "Current start save" : "Use as start save";
  }

  function renderLayers() {
    if (!state.project) return;
    const query = elements.layerSearch.value.trim().toLowerCase();
    const minimum = Number(elements.confidenceFilter.value);
    const rows = state.project.objects
      .filter((object) => {
        const label = `${typeName(object.type_id)} ${object.id}`.toLowerCase();
        return (!query || label.includes(query)) && (object.score == null || object.score >= minimum);
      })
      .slice(0, 500);
    elements.layerList.innerHTML = rows.map((object) => `
      <button class="layer-item ${object.id === state.selectedId ? "active" : ""} ${object.enabled ? "" : "disabled"}"
              data-object-id="${object.id}">
        <span class="type-swatch" style="background:${COLORS[object.type_id] || "#bbb"}"></span>
        <span class="layer-label">${prettyName(typeName(object.type_id))}</span>
        <span class="layer-coordinate">${object.x},${object.y}</span>
      </button>`).join("");
    elements.layerList.querySelectorAll("[data-object-id]").forEach((button) => {
      button.addEventListener("click", () => selectObject(button.dataset.objectId));
    });
  }

  function renderCounts() {
    const enabled = state.project.objects.filter((object) => object.enabled).length;
    elements.objectCount.textContent = `${enabled} objects`;
    elements.statusText.textContent = state.dirty ? "Unsaved corrections" : "Ready";
  }

  async function updatePreview() {
    if (!state.project) return;
    try {
      const response = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.project),
      });
      if (!response.ok) throw new Error((await responseJson(response)).error);
      const blob = await response.blob();
      if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = URL.createObjectURL(blob);
      elements.mapLayer.src = state.previewUrl;
    } catch (error) {
      toast(error.message || String(error), true);
    }
  }

  function schedulePreview(delay = 140) {
    window.clearTimeout(state.previewTimer);
    state.previewTimer = window.setTimeout(updatePreview, delay);
  }

  function mutate(operation, options = {}) {
    if (!state.project) return;
    if (options.snapshot !== false) {
      state.undo.push(JSON.stringify(state.project));
      if (state.undo.length > 60) state.undo.shift();
      state.redo = [];
    }
    operation();
    state.dirty = true;
    renderAll();
    schedulePreview();
  }

  function undo() {
    if (!state.undo.length || !state.project) return;
    state.redo.push(JSON.stringify(state.project));
    state.project = JSON.parse(state.undo.pop());
    if (!state.project.objects.some((object) => object.id === state.selectedId)) state.selectedId = null;
    state.dirty = true;
    syncSettings();
    renderAll();
    schedulePreview(0);
  }

  function redo() {
    if (!state.redo.length || !state.project) return;
    state.undo.push(JSON.stringify(state.project));
    state.project = JSON.parse(state.redo.pop());
    state.dirty = true;
    syncSettings();
    renderAll();
    schedulePreview(0);
  }

  function selectObject(id) {
    state.selectedId = id;
    if (window.matchMedia("(max-width: 720px)").matches) {
      setMobilePanel("right", true);
    }
    renderAll();
  }

  function toggleMobilePanel(side) {
    const className = `mobile-${side}-open`;
    setMobilePanel(side, !document.body.classList.contains(className));
  }

  function setMobilePanel(side, open) {
    document.body.classList.toggle(`mobile-${side}-open`, open);
    if (open) {
      const other = side === "left" ? "right" : "left";
      document.body.classList.remove(`mobile-${other}-open`);
    }
    elements.mobilePaletteButton.setAttribute(
      "aria-pressed",
      String(document.body.classList.contains("mobile-left-open")),
    );
    elements.mobileInspectorButton.setAttribute(
      "aria-pressed",
      String(document.body.classList.contains("mobile-right-open")),
    );
  }

  function selectedObject() {
    return state.project?.objects.find((object) => object.id === state.selectedId) || null;
  }

  function updateSelectedFromInspector() {
    const object = selectedObject();
    if (!object) return;
    const values = {
      type: Number(elements.objectTypeSelect.value),
      x: snap(Number(elements.objectX.value)),
      y: snap(Number(elements.objectY.value)),
      enabled: elements.objectEnabled.checked,
    };
    mutate(() => {
      object.type_id = values.type;
      object.type_name = typeName(values.type);
      object.x = values.x;
      object.y = values.y;
      object.enabled = values.enabled;
    });
  }

  function disableSelected() {
    const object = selectedObject();
    if (!object) return;
    mutate(() => {
      object.enabled = false;
      if (state.project.start.save_id === object.id) state.project.start.save_id = null;
    });
  }

  function duplicateSelected() {
    const object = selectedObject();
    if (!object) return;
    mutate(() => {
      const copy = structuredClone(object);
      copy.id = nextObjectId();
      copy.x += Number(elements.snapSelect.value);
      copy.y += Number(elements.snapSelect.value);
      copy.source = "manual";
      copy.score = null;
      copy.detection_kind = null;
      state.project.objects.push(copy);
      state.selectedId = copy.id;
    });
  }

  function chooseSelectedStart() {
    const object = selectedObject();
    if (!object || !SAVE_TYPES.has(object.type_id) || !object.enabled) return;
    mutate(() => {
      state.project.start.save_id = object.id;
      state.project.start.position = null;
      state.project.start.policy = "none";
    });
    syncSettings();
  }

  function updateSettings() {
    if (!state.project) return;
    mutate(() => { state.project.jmap.infinite_jump = elements.infiniteJump.checked ? 1 : 0; });
  }

  function updateStartPolicy() {
    if (!state.project) return;
    mutate(() => {
      state.project.start.policy = elements.startPolicy.value;
      if (elements.startPolicy.value === "auto") {
        state.project.start.save_id = null;
        state.project.start.position = null;
      }
    });
  }

  function syncSettings() {
    if (!state.project) return;
    elements.infiniteJump.checked = Boolean(state.project.jmap.infinite_jump);
    elements.startPolicy.value = state.project.start.save_id ? "none" : state.project.start.policy;
  }

  function replaceAllWater() {
    if (!state.project) return;
    const replacement = Number(elements.bulkWater.value);
    mutate(() => {
      for (const object of state.project.objects) {
        if (object.enabled && WATER_TYPES.has(object.type_id)) {
          object.type_id = replacement;
          object.type_name = typeName(replacement);
        }
      }
    });
    toast(`All water changed to ${prettyName(typeName(replacement))}`);
  }

  function onPointerDown(event) {
    if (!state.project) return;
    const point = eventPoint(event);
    const hit = hitTest(point.x, point.y);
    elements.interactionLayer.setPointerCapture(event.pointerId);
    if (state.tool === "add") {
      addObject(point.x, point.y);
      return;
    }
    if (state.tool === "erase") {
      if (hit) {
        selectObject(hit.id);
        disableSelected();
      }
      return;
    }
    if (!hit) {
      state.selectedId = null;
      renderAll();
      return;
    }
    selectObject(hit.id);
    state.drag = {
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      objectX: hit.x,
      objectY: hit.y,
      before: JSON.stringify(state.project),
      moved: false,
    };
  }

  function onPointerMove(event) {
    const point = eventPoint(event);
    elements.coordinateText.textContent = `x ${Math.round(point.x)}, y ${Math.round(point.y)}`;
    if (!state.drag || state.drag.pointerId !== event.pointerId) return;
    const object = selectedObject();
    if (!object) return;
    object.x = snap(state.drag.objectX + point.x - state.drag.startX);
    object.y = snap(state.drag.objectY + point.y - state.drag.startY);
    state.drag.moved = object.x !== state.drag.objectX || object.y !== state.drag.objectY;
    state.dirty = state.dirty || state.drag.moved;
    renderOverlay();
    renderInspector();
    renderCounts();
    schedulePreview();
  }

  function onPointerUp(event) {
    if (!state.drag || state.drag.pointerId !== event.pointerId) return;
    if (state.drag.moved) {
      state.undo.push(state.drag.before);
      if (state.undo.length > 60) state.undo.shift();
      state.redo = [];
      renderAll();
    }
    state.drag = null;
  }

  function addObject(x, y) {
    mutate(() => {
      const object = {
        id: nextObjectId(),
        x: snap(x),
        y: snap(y),
        type_id: state.selectedType,
        type_name: typeName(state.selectedType),
        enabled: true,
        source: "manual",
      };
      state.project.objects.push(object);
      state.selectedId = object.id;
    });
  }

  function nextObjectId() {
    let maximum = 0;
    for (const object of state.project.objects) {
      const match = /^obj-(\d+)$/.exec(object.id);
      if (match) maximum = Math.max(maximum, Number(match[1]));
    }
    return `obj-${String(maximum + 1).padStart(4, "0")}`;
  }

  function hitTest(x, y) {
    const objects = [...state.project.objects].reverse();
    return objects.find((object) => {
      const size = objectSize(object.type_id);
      return x >= object.x && y >= object.y && x <= object.x + size && y <= object.y + size;
    }) || null;
  }

  function eventPoint(event) {
    const rect = elements.interactionLayer.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * ROOM_WIDTH / rect.width,
      y: (event.clientY - rect.top) * ROOM_HEIGHT / rect.height,
    };
  }

  function snap(value) {
    const step = Number(elements.snapSelect.value);
    return Math.round(value / step) * step;
  }

  function objectSize(typeId) {
    return MINI_TYPES.has(typeId) ? 16 : 32;
  }

  function setTool(tool) {
    state.tool = tool;
    document.querySelectorAll("[data-tool]").forEach((button) => {
      button.classList.toggle("active", button.dataset.tool === tool);
    });
    elements.interactionLayer.style.cursor = tool === "add" ? "crosshair" : tool === "erase" ? "not-allowed" : "default";
  }

  function setView(view) {
    state.view = view;
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
    });
    elements.sourceLayer.style.opacity = view === "source" ? "1" : view === "blend" ? ".5" : "0";
    elements.mapLayer.style.opacity = view === "source" ? "0" : view === "blend" ? ".58" : "1";
  }

  function setZoom(value) {
    state.zoom = Math.max(0.3, Math.min(2, Math.round(value * 10) / 10));
    elements.stage.style.transform = `scale(${state.zoom})`;
    elements.stage.style.marginBottom = `${24 + ROOM_HEIGHT * (state.zoom - 1)}px`;
    elements.zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
  }

  function fitZoom(center = true) {
    const viewport = elements.stageViewport;
    const zoom = Math.min((viewport.clientWidth - 36) / ROOM_WIDTH, (viewport.clientHeight - 36) / ROOM_HEIGHT, 1);
    setZoom(Math.max(0.3, Math.floor(zoom * 10) / 10));
    if (center) {
      viewport.scrollLeft = Math.max(0, (viewport.scrollWidth - viewport.clientWidth) / 2);
      viewport.scrollTop = 0;
    }
  }

  function setTab(side, name) {
    document.querySelectorAll(`[data-${side}-tab]`).forEach((button) => {
      button.classList.toggle("active", button.dataset[`${side}Tab`] === name);
    });
    if (side === "left") {
      elements.objectsTab.classList.toggle("hidden", name !== "objects");
      elements.scanTab.classList.toggle("hidden", name !== "scan");
    } else {
      elements.inspectorTab.classList.toggle("hidden", name !== "inspector");
      elements.layersTab.classList.toggle("hidden", name !== "layers");
    }
  }

  async function downloadJmap() {
    if (!state.project) return;
    setBusy(true, "Preparing JTool map");
    try {
      const response = await fetch("/api/export-jmap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.project),
      });
      if (!response.ok) throw new Error((await responseJson(response)).error);
      downloadBlob(await response.blob(), baseName(".jmap"));
      state.dirty = false;
      renderCounts();
      toast("JTool map downloaded");
    } catch (error) {
      toast(error.message || String(error), true);
    } finally {
      setBusy(false);
    }
  }

  function downloadProject() {
    if (!state.project) return;
    const blob = new Blob([`${JSON.stringify(state.project, null, 2)}\n`], { type: "application/json" });
    downloadBlob(blob, baseName(".jscan.json"));
    state.dirty = false;
    renderCounts();
    toast("Correction project downloaded");
  }

  function baseName(extension) {
    const current = elements.documentName.textContent
      .replace(/\.jscan\.json$/i, "")
      .replace(/\.jmap$/i, "")
      .replace(/\.png$/i, "") || "scan";
    return `${current}${extension}`;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function onKeyDown(event) {
    if (event.target.matches("input, select, textarea")) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      event.shiftKey ? redo() : undo();
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
      event.preventDefault();
      redo();
    } else if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      disableSelected();
    } else if (event.key.toLowerCase() === "v") setTool("select");
    else if (event.key.toLowerCase() === "a") setTool("add");
    else if (event.key.toLowerCase() === "e") setTool("erase");
  }

  function typeName(typeId) {
    return state.metadata?.object_types.find((item) => item.id === typeId)?.name || `unknown_${typeId}`;
  }

  function prettyName(name) {
    return String(name || "").split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
  }

  function setBusy(busy, title = "Working") {
    elements.busyTitle.textContent = title;
    elements.busyOverlay.classList.toggle("hidden", !busy);
  }

  function toast(message, error = false) {
    const node = document.createElement("div");
    node.className = `toast ${error ? "error" : ""}`;
    node.textContent = message;
    elements.toastRegion.appendChild(node);
    window.setTimeout(() => node.remove(), 4200);
  }

  async function apiJson(url) {
    return responseJson(await fetch(url));
  }

  async function responseJson(response) {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }
})();
