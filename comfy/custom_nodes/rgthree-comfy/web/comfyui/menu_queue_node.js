import { app } from "../../scripts/app.js";
import { rgthree } from "./rgthree.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
function getOutputNodes(nodes) {
    return ((nodes === null || nodes === void 0 ? void 0 : nodes.filter((n) => {
        var _a;
        return (n.mode != LiteGraph.NEVER &&
            ((_a = n.constructor.nodeData) === null || _a === void 0 ? void 0 : _a.output_node));
    })) || []);
}
function showQueueNodesMenuIfOutputNodesAreSelected(existingOptions) {
    if (CONFIG_SERVICE.getConfigValue("features.menu_queue_selected_nodes") === false) {
        return;
    }
    const outputNodes = getOutputNodes(Object.values(app.canvas.selected_nodes));
    const menuItem = {
        content: `Queue Selected Output Nodes (rgthree) &nbsp;`,
        className: "rgthree-contextmenu-item",
        callback: () => {
            rgthree.queueOutputNodes(outputNodes.map((n) => n.id));
        },
        disabled: !outputNodes.length,
    };
    let idx = existingOptions.findIndex((o) => (o === null || o === void 0 ? void 0 : o.content) === "Outputs") + 1;
    idx = idx || existingOptions.findIndex((o) => (o === null || o === void 0 ? void 0 : o.content) === "Align") + 1;
    idx = idx || 3;
    existingOptions.splice(idx, 0, menuItem);
}
function showQueueGroupNodesMenuIfGroupIsSelected(existingOptions) {
    if (CONFIG_SERVICE.getConfigValue("features.menu_queue_selected_nodes") === false) {
        return;
    }
    const group = rgthree.lastAdjustedMouseEvent &&
        app.graph.getGroupOnPos(rgthree.lastAdjustedMouseEvent.canvasX, rgthree.lastAdjustedMouseEvent.canvasY);
    const outputNodes = group && getOutputNodes(group._nodes);
    const menuItem = {
        content: `Queue Group Output Nodes (rgthree) &nbsp;`,
        className: "rgthree-contextmenu-item",
        callback: () => {
            outputNodes && rgthree.queueOutputNodes(outputNodes.map((n) => n.id));
        },
        disabled: !(outputNodes === null || outputNodes === void 0 ? void 0 : outputNodes.length),
    };
    let idx = existingOptions.findIndex((o) => { var _a; return (_a = o === null || o === void 0 ? void 0 : o.content) === null || _a === void 0 ? void 0 : _a.startsWith("Queue Selected "); }) + 1;
    idx = idx || existingOptions.findIndex((o) => (o === null || o === void 0 ? void 0 : o.content) === "Outputs") + 1;
    idx = idx || existingOptions.findIndex((o) => (o === null || o === void 0 ? void 0 : o.content) === "Align") + 1;
    idx = idx || 3;
    existingOptions.splice(idx, 0, menuItem);
}
app.registerExtension({
    name: "rgthree.QueueNode",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
            getExtraMenuOptions ? getExtraMenuOptions.apply(this, arguments) : undefined;
            showQueueNodesMenuIfOutputNodesAreSelected(options);
            showQueueGroupNodesMenuIfGroupIsSelected(options);
        };
    },
    async setup() {
        const getCanvasMenuOptions = LGraphCanvas.prototype.getCanvasMenuOptions;
        LGraphCanvas.prototype.getCanvasMenuOptions = function (...args) {
            const options = getCanvasMenuOptions.apply(this, [...args]);
            showQueueNodesMenuIfOutputNodesAreSelected(options);
            showQueueGroupNodesMenuIfGroupIsSelected(options);
            return options;
        };
    },
});
