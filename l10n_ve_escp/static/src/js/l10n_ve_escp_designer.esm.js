import {Component, onMounted, onWillStart, onWillUnmount, useRef, useState} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

const CELL_W = 7;
const CELL_H = 16;
const BAND_BAR_H = 22;
const HISTORY_LIMIT = 60;

const OBJECT_DEFAULTS = {
    label: {kind: "label", width: 12, text: "Etiqueta", style: "bold"},
    field: {kind: "field", width: 20, expr: "o.display_name", style: "normal"},
    hline: {kind: "hline", width: 40, fill_char: "-", style: "normal"},
};

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

export class L10nVeEscpDesigner extends Component {
    static template = "l10n_ve_escp.Designer";
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.canvasRef = useRef("canvas");
        this.reportId = this.props.action.params?.report_id || this.props.action.context?.active_id;
        this.tempId = -1;
        this.history = [];
        this.drag = null;
        this.state = useState({
            loading: true,
            dirty: false,
            report: {},
            bands: [],
            options: {band_types: [], styles: [], kinds: [], formats: [], aligns: []},
            sampleValues: {},
            deletedObjectIds: [],
            deletedBandIds: [],
            selectedId: null,
            selectedBandId: null,
            zoom: 1,
            showSample: true,
            newBandType: "page_header",
            canUndo: false,
            shiftLines: 2,
            shiftMargin: false,
        });
        this.onPointerMove = this.onPointerMove.bind(this);
        this.onPointerUp = this.onPointerUp.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
        onWillStart(() => this.load());
        onMounted(() => {
            window.addEventListener("pointermove", this.onPointerMove);
            window.addEventListener("pointerup", this.onPointerUp);
        });
        onWillUnmount(() => {
            window.removeEventListener("pointermove", this.onPointerMove);
            window.removeEventListener("pointerup", this.onPointerUp);
        });
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------

    async load() {
        if (!this.reportId) {
            this.notification.add(_t("Falta el reporte a diseñar."), {type: "danger"});
            return;
        }
        const data = await this.orm.call("l10n.ve.escp.report", "designer_load", [[this.reportId]]);
        this.applyData(data);
        this.state.loading = false;
    }

    applyData(data) {
        this.state.report = data.report || {};
        this.state.bands = (data.bands || []).map((band) => ({
            ...band,
            objects: band.objects || [],
        }));
        this.state.options = data.options || {
            band_types: [],
            styles: [],
            kinds: [],
            formats: [],
            aligns: [],
        };
        this.state.sampleValues = data.sample_values || {};
        this.state.deletedObjectIds = [];
        this.state.deletedBandIds = [];
        this.state.dirty = false;
        this.history = [];
        this.state.canUndo = false;
        if (this.state.selectedId && !this.findObject(this.state.selectedId)) {
            this.state.selectedId = null;
        }
    }

    async save() {
        const payload = {
            bands: this.state.bands.map((band) => ({
                id: band.id,
                band_type: band.band_type,
                height: band.height,
                detail_expr: band.detail_expr || false,
                detail_rows: band.detail_rows || 0,
                objects: (band.objects || []).map((obj) => ({
                    ...obj,
                    id: obj.id > 0 ? obj.id : 0,
                })),
            })),
            deleted_object_ids: this.state.deletedObjectIds,
            deleted_band_ids: this.state.deletedBandIds,
            margin_top_lines: this.state.report.margin_top_lines,
        };
        try {
            const data = await this.orm.call("l10n.ve.escp.report", "designer_save", [
                [this.reportId],
                payload,
            ]);
            this.applyData(data);
            this.notification.add(_t("Diseño guardado."), {type: "success"});
        } catch (error) {
            this.notification.add(error?.data?.message || String(error), {type: "danger"});
        }
    }

    async discard() {
        if (!this.state.dirty) {
            return;
        }
        await this.load();
    }

    async openReportForm() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "l10n.ve.escp.report",
            res_id: this.reportId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async preview() {
        if (this.state.dirty) {
            await this.save();
        }
        try {
            const action = await this.orm.call("l10n.ve.escp.report", "action_preview_sample", [
                [this.reportId],
            ]);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error?.data?.message || String(error), {type: "danger"});
        }
    }

    async printTest() {
        if (this.state.dirty) {
            await this.save();
        }
        try {
            const action = await this.orm.call("l10n.ve.escp.report", "action_print_sample", [
                [this.reportId],
            ]);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error?.data?.message || String(error), {type: "danger"});
        }
    }

    async exportLayout() {
        if (this.state.dirty) {
            await this.save();
        }
        try {
            const result = await this.orm.call(
                "l10n.ve.escp.report",
                "download_layout_export",
                [[this.reportId]]
            );
            const blob = new Blob([result.content], {type: "application/json;charset=utf-8"});
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = result.filename || "reporte.escp.json";
            link.click();
            URL.revokeObjectURL(url);
            this.notification.add(_t("Diseño exportado."), {type: "success"});
        } catch (error) {
            this.notification.add(error?.data?.message || String(error), {type: "danger"});
        }
    }

    shiftAll(direction) {
        const lines = Math.max(1, parseInt(this.state.shiftLines, 10) || 2);
        const delta = direction === "up" ? -lines : lines;
        this.snapshot();
        for (const band of this.state.bands) {
            for (const obj of band.objects || []) {
                obj.row = Math.max(0, obj.row + delta);
                this.enforceBounds(obj, band);
            }
        }
        if (this.state.shiftMargin) {
            this.state.report.margin_top_lines = Math.max(
                0,
                (this.state.report.margin_top_lines || 0) + delta
            );
        }
    }

    // ------------------------------------------------------------------
    // History
    // ------------------------------------------------------------------

    snapshot() {
        this.history.push(
            clone({
                bands: this.state.bands,
                deletedObjectIds: this.state.deletedObjectIds,
                deletedBandIds: this.state.deletedBandIds,
            })
        );
        if (this.history.length > HISTORY_LIMIT) {
            this.history.shift();
        }
        this.state.dirty = true;
        this.state.canUndo = true;
    }

    undo() {
        const snap = this.history.pop();
        if (!snap) {
            return;
        }
        this.state.bands = snap.bands;
        this.state.deletedObjectIds = snap.deletedObjectIds;
        this.state.deletedBandIds = snap.deletedBandIds;
        this.state.dirty = true;
        this.state.canUndo = this.history.length > 0;
        if (this.state.selectedId && !this.findObject(this.state.selectedId)) {
            this.state.selectedId = null;
        }
    }

    // ------------------------------------------------------------------
    // Geometry
    // ------------------------------------------------------------------

    get zoomPercent() {
        return Math.round(this.state.zoom * 100);
    }

    get cellW() {
        return CELL_W * this.state.zoom;
    }

    get cellH() {
        return CELL_H * this.state.zoom;
    }

    get canvasWidth() {
        return (this.state.report.line_width || 80) * this.cellW;
    }

    get columns() {
        const width = this.state.report.line_width || 80;
        return Array.from({length: Math.ceil(width / 10)}, (_v, index) => index * 10);
    }

    get usedRows() {
        const report = this.state.report;
        let rows = report.margin_top_lines || 0;
        for (const band of this.state.bands) {
            if (band.band_type === "detail") {
                const detailRows = band.detail_rows || report.detail_rows || 1;
                rows += (band.height || 1) * detailRows;
            } else {
                rows += band.height || 0;
            }
        }
        return rows;
    }

    bandLabel(bandType) {
        const found = this.state.options.band_types.find(([key]) => key === bandType);
        return found ? found[1] : bandType;
    }

    bandStyle(band) {
        return `height: ${band.height * this.cellH}px; width: ${this.canvasWidth}px; background-size: ${this.cellW}px ${this.cellH}px;`;
    }

    bandRows(band) {
        return Array.from({length: band.height}, (_v, index) => index);
    }

    objectStyle(obj) {
        return (
            `left: ${obj.col * this.cellW}px; top: ${obj.row * this.cellH}px; ` +
            `width: ${Math.max(1, obj.width) * this.cellW}px; height: ${Math.max(1, obj.height) * this.cellH}px;`
        );
    }

    objectText(obj) {
        if (obj.kind === "hline") {
            return (obj.fill_char || "-").repeat(Math.max(1, obj.width));
        }
        if (obj.kind === "label") {
            return obj.text || "";
        }
        if (this.state.showSample && obj.id in this.state.sampleValues) {
            return this.state.sampleValues[obj.id];
        }
        return obj.expr || "";
    }

    objectClasses(obj) {
        const classes = ["o_escp_dsg_object", `o_escp_dsg_kind_${obj.kind}`];
        if (obj.id === this.state.selectedId) {
            classes.push("o_escp_dsg_selected");
        }
        if (!obj.active) {
            classes.push("o_escp_dsg_inactive");
        }
        if ((obj.style || "").includes("bold")) {
            classes.push("o_escp_dsg_bold");
        }
        if ((obj.style || "").includes("wide")) {
            classes.push("o_escp_dsg_wide");
        }
        if ((obj.style || "").includes("underline")) {
            classes.push("o_escp_dsg_underline");
        }
        if ((obj.style || "").includes("small")) {
            classes.push("o_escp_dsg_small");
        }
        classes.push(`o_escp_dsg_align_${obj.align || "left"}`);
        return classes.join(" ");
    }

    // ------------------------------------------------------------------
    // Selection helpers
    // ------------------------------------------------------------------

    findObject(id) {
        for (const band of this.state.bands) {
            const obj = band.objects.find((item) => item.id === id);
            if (obj) {
                return {band, obj};
            }
        }
        return null;
    }

    get selected() {
        return this.state.selectedId ? this.findObject(this.state.selectedId) : null;
    }

    get selectedObject() {
        return this.selected?.obj || null;
    }

    get selectedBand() {
        if (this.state.selectedBandId) {
            return this.state.bands.find((band) => band.id === this.state.selectedBandId) || null;
        }
        return null;
    }

    selectObject(obj, band) {
        this.state.selectedId = obj.id;
        this.state.selectedBandId = band.id;
    }

    selectBand(band) {
        this.state.selectedId = null;
        this.state.selectedBandId = band.id;
    }

    // ------------------------------------------------------------------
    // Mutations
    // ------------------------------------------------------------------

    addObject(kind) {
        const band =
            this.selectedBand ||
            this.state.bands.find((item) => item.band_type === "page_header") ||
            this.state.bands[0];
        if (!band) {
            this.notification.add(_t("Cree primero una banda."), {type: "warning"});
            return;
        }
        this.snapshot();
        const obj = {
            id: this.tempId--,
            kind,
            row: 0,
            col: 0,
            width: 10,
            height: 1,
            align: "left",
            style: "normal",
            text: false,
            expr: false,
            format: "text",
            digits: 2,
            currency_expr: false,
            wrap: false,
            print_when: false,
            fill_char: "-",
            foxpro_expr: false,
            active: true,
            sequence: band.objects.length * 10,
            ...OBJECT_DEFAULTS[kind],
        };
        band.objects.push(obj);
        this.selectObject(obj, band);
    }

    duplicateSelected() {
        const found = this.selected;
        if (!found) {
            return;
        }
        this.snapshot();
        const copy = {...clone(found.obj), id: this.tempId--, row: found.obj.row + 1};
        found.band.objects.push(copy);
        this.selectObject(copy, found.band);
    }

    deleteSelected() {
        const found = this.selected;
        if (!found) {
            return;
        }
        this.snapshot();
        found.band.objects = found.band.objects.filter((item) => item.id !== found.obj.id);
        if (found.obj.id > 0) {
            this.state.deletedObjectIds.push(found.obj.id);
        }
        this.state.selectedId = null;
    }

    addBand() {
        const bandType = this.state.newBandType;
        if (this.state.bands.some((band) => band.band_type === bandType)) {
            this.notification.add(_t("Ya existe una banda de ese tipo."), {type: "warning"});
            return;
        }
        this.snapshot();
        const order = (this.state.options.band_types || []).map(([key]) => key);
        const band = {
            id: this.tempId--,
            band_type: bandType,
            height: bandType === "detail" ? 1 : 3,
            detail_expr: bandType === "detail" ? "o.line_ids" : false,
            detail_rows: 0,
            objects: [],
        };
        this.state.bands.push(band);
        this.state.bands.sort((a, b) => order.indexOf(a.band_type) - order.indexOf(b.band_type));
        this.selectBand(band);
    }

    deleteBand(band) {
        if (!band) {
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Eliminar banda"),
            body: _t("Se eliminará la banda %s y sus %s objetos. ¿Continuar?", this.bandLabel(band.band_type), band.objects.length),
            confirmLabel: _t("Eliminar"),
            confirm: () => this.removeBand(band),
            cancel: () => null,
        });
    }

    removeBand(band) {
        if (!band) {
            return;
        }
        this.snapshot();
        for (const obj of band.objects) {
            if (obj.id > 0) {
                this.state.deletedObjectIds.push(obj.id);
            }
        }
        if (band.id > 0) {
            this.state.deletedBandIds.push(band.id);
        }
        this.state.bands = this.state.bands.filter((item) => item.id !== band.id);
        this.state.selectedId = null;
        this.state.selectedBandId = null;
    }

    updateSelected(field, value) {
        const obj = this.selectedObject;
        if (!obj) {
            return;
        }
        this.snapshot();
        obj[field] = value;
        this.enforceBounds(obj, this.selected.band);
    }

    updateBand(band, field, value) {
        this.snapshot();
        band[field] = value;
        if (field === "height") {
            band.height = Math.max(1, parseInt(value, 10) || 1);
            for (const obj of band.objects) {
                this.enforceBounds(obj, band);
            }
        }
    }

    updateReportMargin(value) {
        this.snapshot();
        this.state.report.margin_top_lines = Math.max(0, parseInt(value, 10) || 0);
    }

    enforceBounds(obj, band) {
        const maxCol = (this.state.report.line_width || 80) - 1;
        obj.width = Math.max(1, parseInt(obj.width, 10) || 1);
        obj.height = Math.max(1, parseInt(obj.height, 10) || 1);
        obj.col = Math.min(Math.max(0, parseInt(obj.col, 10) || 0), maxCol);
        obj.row = Math.max(0, parseInt(obj.row, 10) || 0);
        if (obj.row + obj.height > band.height) {
            band.height = obj.row + obj.height;
        }
        if (obj.col + obj.width > maxCol + 1) {
            obj.width = maxCol + 1 - obj.col;
        }
    }

    // ------------------------------------------------------------------
    // Pointer interactions
    // ------------------------------------------------------------------

    onObjectPointerDown(ev, obj, band, mode = "move") {
        ev.stopPropagation();
        ev.preventDefault();
        this.selectObject(obj, band);
        this.drag = {
            mode,
            objId: obj.id,
            startX: ev.clientX,
            startY: ev.clientY,
            startRow: obj.row,
            startCol: obj.col,
            startWidth: obj.width,
            startHeight: obj.height,
            snapshotTaken: false,
        };
        this.canvasRef.el?.focus();
    }

    onBandHandlePointerDown(ev, band) {
        ev.stopPropagation();
        ev.preventDefault();
        this.selectBand(band);
        this.drag = {
            mode: "band",
            bandId: band.id,
            startY: ev.clientY,
            startHeight: band.height,
            snapshotTaken: false,
        };
    }

    onPointerMove(ev) {
        const drag = this.drag;
        if (!drag) {
            return;
        }
        const dCol = Math.round((ev.clientX - drag.startX) / this.cellW);
        const dRow = Math.round((ev.clientY - drag.startY) / this.cellH);
        if (!dCol && !dRow) {
            return;
        }
        if (!drag.snapshotTaken) {
            this.snapshot();
            drag.snapshotTaken = true;
        }
        if (drag.mode === "band") {
            const band = this.state.bands.find((item) => item.id === drag.bandId);
            if (band) {
                const minHeight = Math.max(
                    1,
                    ...band.objects.map((obj) => obj.row + obj.height)
                );
                band.height = Math.max(minHeight, drag.startHeight + dRow);
            }
            return;
        }
        const found = this.findObject(drag.objId);
        if (!found) {
            return;
        }
        const {obj, band} = found;
        if (drag.mode === "move") {
            obj.col = drag.startCol + dCol;
            obj.row = drag.startRow + dRow;
            this.moveAcrossBands(obj, band, ev.clientY);
        } else if (drag.mode === "resize-w") {
            obj.width = drag.startWidth + dCol;
        } else if (drag.mode === "resize-h") {
            obj.height = drag.startHeight + dRow;
        }
        const current = this.findObject(obj.id);
        this.enforceBounds(current.obj, current.band);
    }

    moveAcrossBands(obj, band, clientY) {
        const canvas = this.canvasRef.el;
        if (!canvas) {
            return;
        }
        const bandEls = canvas.querySelectorAll(".o_escp_dsg_band_body");
        for (const el of bandEls) {
            const rect = el.getBoundingClientRect();
            if (clientY >= rect.top && clientY < rect.bottom) {
                const targetId = Number(el.dataset.bandId);
                if (targetId !== band.id) {
                    const target = this.state.bands.find((item) => item.id === targetId);
                    if (!target) {
                        return;
                    }
                    band.objects = band.objects.filter((item) => item.id !== obj.id);
                    obj.row = Math.max(0, Math.floor((clientY - rect.top) / this.cellH));
                    target.objects.push(obj);
                    this.state.selectedBandId = target.id;
                    this.drag.startRow = obj.row;
                    this.drag.startY = clientY;
                }
                return;
            }
        }
    }

    onPointerUp() {
        this.drag = null;
    }

    onCanvasPointerDown(ev, band) {
        if (ev.target.closest(".o_escp_dsg_object")) {
            return;
        }
        this.selectBand(band);
    }

    onKeyDown(ev) {
        if (ev.target.closest("input, textarea, select")) {
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") {
            ev.preventDefault();
            this.undo();
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
            ev.preventDefault();
            this.save();
            return;
        }
        const found = this.selected;
        if (!found) {
            return;
        }
        const step = {ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0]}[
            ev.key
        ];
        if (step) {
            ev.preventDefault();
            this.snapshot();
            if (ev.shiftKey) {
                found.obj.width += step[1];
                found.obj.height += step[0];
            } else {
                found.obj.row += step[0];
                found.obj.col += step[1];
            }
            this.enforceBounds(found.obj, found.band);
        } else if (ev.key === "Delete" || ev.key === "Backspace") {
            ev.preventDefault();
            this.deleteSelected();
        } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "d") {
            ev.preventDefault();
            this.duplicateSelected();
        }
    }

    intValue(ev, fallback = 0) {
        const value = parseInt(ev.target.value, 10);
        return Number.isNaN(value) ? fallback : value;
    }

    zoomIn() {
        this.state.zoom = Math.min(3, Math.round((this.state.zoom + 0.25) * 100) / 100);
    }

    zoomOut() {
        this.state.zoom = Math.max(0.5, Math.round((this.state.zoom - 0.25) * 100) / 100);
    }
}

registry.category("actions").add("l10n_ve_escp_designer", L10nVeEscpDesigner);
