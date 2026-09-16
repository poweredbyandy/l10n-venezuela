import {Component, markup, onMounted, onWillUnmount, useRef} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const MODAL_CLASS = "o_l10n_ve_escp_preview_modal";

export class L10nVeEscpPreviewField extends Component {
    static template = "l10n_ve_escp.PreviewField";
    static props = {
        ...standardFieldProps,
        htmlField: {type: String, optional: true},
    };

    setup() {
        this.rootRef = useRef("root");
        this.pdfRef = useRef("pdf");
        this.blobUrl = null;
        this.blobSource = null;
        this.modalEl = null;
        this.resizeObserver = null;
        onMounted(() => {
            this.enlargeDialog();
            this.scheduleResize();
            const modalContent = this.rootRef.el?.closest(".modal-content");
            if (modalContent && typeof ResizeObserver !== "undefined") {
                this.resizeObserver = new ResizeObserver(() => this.scheduleResize());
                this.resizeObserver.observe(modalContent);
            }
        });
        onWillUnmount(() => {
            this.resizeObserver?.disconnect();
            this.revokeBlob();
            if (this.modalEl) {
                this.modalEl.classList.remove(MODAL_CLASS);
            }
        });
    }

    scheduleResize() {
        requestAnimationFrame(() => {
            this.resizePreview();
            requestAnimationFrame(() => this.resizePreview());
        });
    }

    enlargeDialog() {
        const modal = this.rootRef.el?.closest(".modal-dialog");
        if (modal) {
            modal.classList.add(MODAL_CLASS);
            this.modalEl = modal;
        }
    }

    resizePreview() {
        const root = this.rootRef.el;
        const modalContent = root?.closest(".modal-content");
        const iframe = this.pdfRef.el;
        if (!root || !modalContent) {
            return;
        }
        const header = modalContent.querySelector(".modal-header");
        const footer = modalContent.querySelector(".modal-footer");
        const height =
            modalContent.clientHeight -
            (header?.offsetHeight || 0) -
            (footer?.offsetHeight || 0) -
            8;
        if (height <= 0) {
            return;
        }
        root.style.height = `${height}px`;
        root.style.minHeight = `${height}px`;
        if (iframe) {
            iframe.style.height = `${height}px`;
            iframe.style.minHeight = `${height}px`;
        }
    }

    revokeBlob() {
        if (this.blobUrl) {
            URL.revokeObjectURL(this.blobUrl);
        }
        this.blobUrl = null;
        this.blobSource = null;
    }

    get pdfUrl() {
        const b64 = this.props.record.data[this.props.name];
        if (!b64) {
            this.revokeBlob();
            return null;
        }
        if (b64 !== this.blobSource) {
            this.revokeBlob();
            const bytes = Uint8Array.from(globalThis.atob(b64), (c) => c.charCodeAt(0));
            const blob = new Blob([bytes], {type: "application/pdf"});
            this.blobUrl = URL.createObjectURL(blob);
            this.blobSource = b64;
        }
        const file = encodeURIComponent(this.blobUrl);
        return `/web/static/lib/pdfjs/web/viewer.html?file=${file}#zoom=page-height&pagemode=none&toolbar=0`;
    }

    get htmlContent() {
        const field = this.props.htmlField;
        return markup((field && this.props.record.data[field]) || "");
    }
}

registry.category("fields").add("l10n_ve_escp_preview", {
    component: L10nVeEscpPreviewField,
    supportedTypes: ["text", "char", "html"],
    extractProps: ({options}) => ({htmlField: options.html_field}),
});
