import { app } from "../../../scripts/app.js";

const EXTENSION_NAME = "ComfyUI.UniResize.UniRatio";
const CATALOG_URL = new URL("./resolution_catalog.json", import.meta.url);
let catalogPromise;

function getCatalog() {
    catalogPromise ??= fetch(CATALOG_URL).then((response) => {
        if (!response.ok) throw new Error(`Unable to load UniRatio catalog (${response.status})`);
        return response.json();
    });
    return catalogPromise;
}

function indexCatalog(catalog) {
    return {
        profiles: new Map(catalog.profiles.map((profile) => [profile.id, profile])),
        ratios: new Map(catalog.ratios.map((ratio) => [ratio.id, ratio])),
    };
}

function translatedDimensions(profile, ratio) {
    const aspect = ratio.width / ratio.height;
    const idealWidth = Math.sqrt(profile.target_area * aspect);
    const idealHeight = Math.sqrt(profile.target_area / aspect);
    const snap = (value) => Math.max(profile.multiple, Math.round(value / profile.multiple) * profile.multiple);
    const baseWidth = snap(idealWidth);
    const baseHeight = snap(idealHeight);
    let best;
    for (let x = -2; x <= 2; x++) {
        for (let y = -2; y <= 2; y++) {
            const width = baseWidth + x * profile.multiple;
            const height = baseHeight + y * profile.multiple;
            if (width < profile.multiple || height < profile.multiple) continue;
            const score = Math.abs(width * height - profile.target_area) / profile.target_area
                + Math.abs(width / height - aspect) / aspect;
            if (!best || score < best.score) best = { score, width, height };
        }
    }
    return [best.width, best.height];
}

function scaledDimensions(dimensions, scale, multiple = 1) {
    const snap = (value) => Math.max(multiple, Math.round(value / multiple) * multiple);
    return [snap(dimensions[0] * scale), snap(dimensions[1] * scale)];
}

function describe(selection, catalog, scale = 1, manualWidth = 1024, manualHeight = 1024) {
    if (selection === "manual") {
        const dimensions = scaledDimensions([manualWidth, manualHeight], scale);
        return { label: "Manual resolution", detail: `${dimensions[0]} × ${dimensions[1]}${scale !== 1 ? ` · ${scale}×` : ""}` };
    }
    const [profileId, ratioId] = String(selection).split(":");
    const { profiles, ratios } = indexCatalog(catalog);
    const profile = profiles.get(profileId);
    const ratio = ratios.get(ratioId);
    if (!profile || !ratio) return { label: String(selection), detail: "Unknown saved preset" };
    const baseDimensions = profile.exact?.[ratioId] ?? translatedDimensions(profile, ratio);
    const dimensions = scaledDimensions(baseDimensions, scale, profile.multiple);
    return {
        label: `${profile.name} · ${ratio.label}`,
        detail: `${dimensions[0]} × ${dimensions[1]} · ${profile.exact?.[ratioId] ? "exact" : "calculated"}${scale !== 1 ? ` · ${scale}×` : ""}`,
    };
}

function addStyles() {
    if (document.getElementById("uniratio-styles")) return;
    const style = document.createElement("style");
    style.id = "uniratio-styles";
    style.textContent = `
        .uniratio-overlay{position:fixed;inset:0;z-index:10000;background:#0009;display:grid;place-items:center;padding:24px}
        .uniratio-panel{width:min(760px,94vw);max-height:min(760px,90vh);display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--border-color,#555);border-radius:12px;background:var(--comfy-menu-bg,#202020);color:var(--input-text,#eee);box-shadow:0 20px 70px #000b;font:13px system-ui,sans-serif}
        .uniratio-head{display:flex;gap:10px;padding:14px;border-bottom:1px solid #ffffff20}.uniratio-search{flex:1;padding:10px 12px;border:1px solid #ffffff28;border-radius:8px;background:#0004;color:inherit;outline:none}.uniratio-close{width:38px;border:0;border-radius:8px;background:#ffffff12;color:inherit;cursor:pointer}
        .uniratio-body{overflow:auto;padding:10px}.uniratio-section{margin:8px 4px 5px;color:#aaa;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}.uniratio-family{margin:5px 0;border:1px solid #ffffff15;border-radius:8px;overflow:hidden}.uniratio-family summary{padding:10px 12px;cursor:pointer;font-weight:650;background:#ffffff08}.uniratio-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:7px;padding:8px}.uniratio-option{padding:9px 10px;text-align:left;border:1px solid #ffffff18;border-radius:7px;background:#ffffff08;color:inherit;cursor:pointer}.uniratio-option:hover,.uniratio-option:focus{border-color:var(--p-primary-color,#7c9cff);background:#ffffff12}.uniratio-option small{display:block;margin-top:3px;color:#aaa}.uniratio-empty{padding:40px;text-align:center;color:#aaa}
        .uniratio-manual{display:grid;grid-template-columns:1fr auto 1fr auto;align-items:end;gap:8px;padding:10px;margin:3px 0 12px;border:1px solid #ffffff18;border-radius:8px;background:#ffffff07}.uniratio-manual label{display:grid;gap:5px;color:#aaa;font-size:11px}.uniratio-manual input{min-width:0;padding:8px;border:1px solid #ffffff25;border-radius:6px;background:#0004;color:inherit}.uniratio-manual button{padding:9px 14px;border:1px solid var(--p-primary-color,#7c9cff);border-radius:7px;background:#ffffff10;color:inherit;cursor:pointer}.uniratio-times{padding-bottom:8px;color:#888}
    `;
    document.head.append(style);
}

async function openPicker(state, onSelect) {
    addStyles();
    const catalog = await getCatalog();
    const ratioMap = new Map(catalog.ratios.map((ratio) => [ratio.id, ratio]));
    const overlay = document.createElement("div");
    overlay.className = "uniratio-overlay";
    overlay.innerHTML = `<div class="uniratio-panel" role="dialog" aria-modal="true" aria-label="Choose a resolution"><div class="uniratio-head"><input class="uniratio-search" type="search" placeholder="Search models, tiers, ratios or dimensions…" autofocus><button class="uniratio-close" title="Close">×</button></div><div class="uniratio-body"></div></div>`;
    document.body.append(overlay);
    const search = overlay.querySelector(".uniratio-search");
    const body = overlay.querySelector(".uniratio-body");
    const close = () => overlay.remove();

    function render(query = "") {
        const needle = query.trim().toLowerCase();
        body.replaceChildren();
        let count = 0;
        const manual = document.createElement("div");
        manual.className = "uniratio-manual";
        manual.innerHTML = `<label>Manual width<input type="number" min="1" max="16384" step="1" value="${state.manualWidth}"></label><span class="uniratio-times">×</span><label>Manual height<input type="number" min="1" max="16384" step="1" value="${state.manualHeight}"></label><button>Use manual</button>`;
        const manualInputs = manual.querySelectorAll("input");
        manual.querySelector("button").onclick = () => {
            const width = Math.max(1, Number.parseInt(manualInputs[0].value, 10) || 1);
            const height = Math.max(1, Number.parseInt(manualInputs[1].value, 10) || 1);
            onSelect("manual", catalog, width, height);
            close();
        };
        body.append(manual);
        for (const section of ["General", "Image", "Video"]) {
            const profiles = catalog.profiles.filter((profile) => profile.section === section);
            const groups = new Map();
            for (const profile of profiles) {
                const options = profile.ratios.map((ratioId) => {
                    const ratio = ratioMap.get(ratioId);
                    const dimensions = profile.exact?.[ratioId] ?? translatedDimensions(profile, ratio);
                    const id = `${profile.id}:${ratioId}`;
                    const haystack = `${section} ${profile.family} ${profile.name} ${profile.tier} ${ratio.label} ${dimensions.join("x")}`.toLowerCase();
                    return { id, ratio, dimensions, exact: Boolean(profile.exact?.[ratioId]), visible: !needle || haystack.includes(needle) };
                }).filter((option) => option.visible);
                if (options.length) groups.set(profile, options);
            }
            if (!groups.size) continue;
            const heading = document.createElement("div");
            heading.className = "uniratio-section";
            heading.textContent = section;
            body.append(heading);
            for (const [profile, options] of groups) {
                const group = document.createElement("details");
                group.className = "uniratio-family";
                group.open = Boolean(needle) || options.some((option) => option.id === state.selection);
                group.innerHTML = `<summary>${profile.name}</summary><div class="uniratio-list"></div>`;
                const list = group.querySelector(".uniratio-list");
                for (const option of options) {
                    const button = document.createElement("button");
                    button.className = "uniratio-option";
                    button.innerHTML = `${option.ratio.label}<small>${option.dimensions[0]} × ${option.dimensions[1]} · ${option.exact ? "exact" : "calculated"}</small>`;
                    button.onclick = () => { onSelect(option.id, catalog); close(); };
                    list.append(button);
                    count++;
                }
                body.append(group);
            }
        }
        if (!count) body.innerHTML = `<div class="uniratio-empty">No matching resolution presets</div>`;
    }

    search.addEventListener("input", () => render(search.value));
    overlay.querySelector(".uniratio-close").onclick = close;
    overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
    overlay.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
    render();
    search.focus();
}

app.registerExtension({
    name: EXTENSION_NAME,
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "UniRatioNode") return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original?.apply(this, arguments);
            const selection = this.widgets?.find((widget) => widget.name === "selection");
            const upscale = this.widgets?.find((widget) => widget.name === "upscale");
            const manualWidth = this.widgets?.find((widget) => widget.name === "manual_width");
            const manualHeight = this.widgets?.find((widget) => widget.name === "manual_height");
            if (!selection || !upscale || !manualWidth || !manualHeight) return result;

            const hiddenWidgets = [selection, manualWidth, manualHeight];
            const hidePresetWidgets = () => {
                for (const widget of hiddenWidgets) {
                    widget.computeSize = () => [0, -4];
                    widget.draw = () => {};
                    widget.type = "uniratio-hidden";
                }
                this.setSize([Math.max(this.size[0], 300), this.computeSize()[1]]);
            };

            const summary = this.addWidget("text", "Resolved", "Loading…", () => {}, { serialize: false });
            summary.disabled = true;
            const choose = this.addWidget("button", "Resolution", "Choose…", async () => {
                await openPicker({ selection: selection.value, manualWidth: manualWidth.value, manualHeight: manualHeight.value }, (value, catalog, width, height) => {
                    selection.value = value;
                    if (value === "manual") {
                        manualWidth.value = width;
                        manualHeight.value = height;
                    }
                    const description = describe(value, catalog, upscale.value, manualWidth.value, manualHeight.value);
                    summary.value = `${description.label} · ${description.detail}`;
                    this.setDirtyCanvas(true, true);
                });
            });

            getCatalog().then((catalog) => {
                const updateSummary = () => {
                    const description = describe(selection.value, catalog, upscale.value, manualWidth.value, manualHeight.value);
                    summary.value = `${description.label} · ${description.detail}`;
                    this.setDirtyCanvas(true, true);
                };
                const originalUpscaleCallback = upscale.callback;
                upscale.callback = function () {
                    originalUpscaleCallback?.apply(this, arguments);
                    updateSummary();
                };
                updateSummary();
                choose.label = "Change resolution";
                hidePresetWidgets();
            }).catch((error) => {
                summary.value = "Catalog unavailable — use saved preset";
                console.error("[UniRatio]", error);
            });

            this.setSize([Math.max(this.size[0], 300), this.computeSize()[1]]);
            return result;
        };
    },
});
