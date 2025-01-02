import { app } from "scripts/app.js";
import { BaseCollectorNode } from "./base_node_collector.js";
import { NodeTypesString, stripRgthree } from "./constants.js";

import type {
  INodeInputSlot,
  INodeOutputSlot,
  LGraphGroup,
  LGraphNode,
  LLink,
  SerializedLGraphNode,
} from "typings/litegraph.js";
import {
  PassThroughFollowing,
  addConnectionLayoutSupport,
  getConnectedInputNodesAndFilterPassThroughs,
  getConnectedOutputNodesAndFilterPassThroughs,
} from "./utils.js";
import { NodeMode } from "typings/comfy.js";

class NodeModeRepeater extends BaseCollectorNode {
  override readonly inputsPassThroughFollowing: PassThroughFollowing = PassThroughFollowing.ALL;

  static override type = NodeTypesString.NODE_MODE_REPEATER;
  static override title = NodeTypesString.NODE_MODE_REPEATER;
  override comfyClass = NodeTypesString.NODE_MODE_REPEATER;

  private hasRelayInput = false;
  private hasTogglerOutput = false;

  constructor(title?: string) {
    super(title);
    this.onConstructed();
  }

  override onConstructed(): boolean {
    this.addOutput("OPT_CONNECTION", "*", {
      color_on: "#Fc0",
      color_off: "#a80",
    });

    return super.onConstructed();
  }

  override configure(info: SerializedLGraphNode<LGraphNode>): void {
    // Patch a small issue (~14h) where multiple OPT_CONNECTIONS may have been created.
    // https://github.com/rgthree/rgthree-comfy/issues/206
    // TODO: This can probably be removed within a few weeks.
    if (info.outputs?.length) {
      info.outputs.length = 1;
    }
    super.configure(info);
  }

  override onConnectOutput(
    outputIndex: number,
    inputType: string | -1,
    inputSlot: INodeInputSlot,
    inputNode: LGraphNode,
    inputIndex: number,
  ): boolean {
    // We can only connect to a a FAST_MUTER or FAST_BYPASSER if we aren't connectged to a relay, since the relay wins.
    let canConnect = !this.hasRelayInput;
    canConnect =
      canConnect && super.onConnectOutput(outputIndex, inputType, inputSlot, inputNode, inputIndex);
    // Output can only connect to a FAST MUTER, FAST BYPASSER, NODE_COLLECTOR OR ACTION BUTTON
    let nextNode = getConnectedOutputNodesAndFilterPassThroughs(this, inputNode)[0] || inputNode;
    return (
      canConnect &&
      [
        NodeTypesString.FAST_MUTER,
        NodeTypesString.FAST_BYPASSER,
        NodeTypesString.NODE_COLLECTOR,
        NodeTypesString.FAST_ACTIONS_BUTTON,
        NodeTypesString.REROUTE,
        NodeTypesString.RANDOM_UNMUTER,
      ].includes(nextNode.type || "")
    );
  }

  override onConnectInput(
    inputIndex: number,
    outputType: string | -1,
    outputSlot: INodeOutputSlot,
    outputNode: LGraphNode,
    outputIndex: number,
  ): boolean {
    // We can only connect to a a FAST_MUTER or FAST_BYPASSER if we aren't connectged to a relay, since the relay wins.
    let canConnect = super.onConnectInput?.(
      inputIndex,
      outputType,
      outputSlot,
      outputNode,
      outputIndex,
    );
    // Output can only connect to a FAST MUTER or FAST BYPASSER
    let nextNode = getConnectedOutputNodesAndFilterPassThroughs(this, outputNode)[0] || outputNode;
    const isNextNodeRelay = nextNode.type === NodeTypesString.NODE_MODE_RELAY;
    return canConnect && (!isNextNodeRelay || !this.hasTogglerOutput);
  }

  override onConnectionsChange(
    type: number,
    slotIndex: number,
    isConnected: boolean,
    linkInfo: LLink,
    ioSlot: INodeOutputSlot | INodeInputSlot,
  ): void {
    super.onConnectionsChange(type, slotIndex, isConnected, linkInfo, ioSlot);

    let hasTogglerOutput = false;
    let hasRelayInput = false;

    const outputNodes = getConnectedOutputNodesAndFilterPassThroughs(this);
    for (const outputNode of outputNodes) {
      if (
        outputNode?.type === NodeTypesString.FAST_MUTER ||
        outputNode?.type === NodeTypesString.FAST_BYPASSER
      ) {
        hasTogglerOutput = true;
        break;
      }
    }

    const inputNodes = getConnectedInputNodesAndFilterPassThroughs(this);
    for (const [index, inputNode] of inputNodes.entries()) {
      if (inputNode?.type === NodeTypesString.NODE_MODE_RELAY) {
        // We can't be connected to a relay if we're connected to a toggler. Something has gone wrong.
        if (hasTogglerOutput) {
          console.log(`Can't be connected to a Relay if also output to a toggler.`);
          this.disconnectInput(index);
        } else {
          hasRelayInput = true;
          if (this.inputs[index]) {
            this.inputs[index]!.color_on = "#FC0";
            this.inputs[index]!.color_off = "#a80";
          }
        }
      } else {
        inputNode.mode = this.mode;
      }
    }

    this.hasTogglerOutput = hasTogglerOutput;
    this.hasRelayInput = hasRelayInput;

    // If we have a relay input, then we should remove the toggler output, or add it if not.
    if (this.hasRelayInput) {
      if (this.outputs[0]) {
        this.disconnectOutput(0);
        this.removeOutput(0);
      }
    } else if (!this.outputs[0]) {
      this.addOutput("OPT_CONNECTION", "*", {
        color_on: "#Fc0",
        color_off: "#a80",
      });
    }
  }

  /** When a mode change, we want all connected nodes to match except for connected relays. */
  override onModeChange(from: NodeMode, to: NodeMode) {
    super.onModeChange(from, to);
    const linkedNodes = getConnectedInputNodesAndFilterPassThroughs(this).filter(
      (node) => node.type !== NodeTypesString.NODE_MODE_RELAY,
    );
    if (linkedNodes.length) {
      for (const node of linkedNodes) {
        if (node.type !== NodeTypesString.NODE_MODE_RELAY) {
          node.mode = this.mode;
        }
      }
    } else if (app.graph._groups?.length) {
      // No linked nodes.. check if we're in a group.
      for (const group of app.graph._groups as LGraphGroup[]) {
        group.recomputeInsideNodes();
        if (group._nodes?.includes(this)) {
          for (const node of group._nodes) {
            node.mode = this.mode;
          }
        }
      }
    }
  }

  override getHelp(): string {
    return `
      <p>
        When this node's mode (Mute, Bypass, Active) changes, it will "repeat" that mode to all
        connected input nodes, or, if there are no connected nodes AND it is overlapping a group,
        "repeat" it's mode to all nodes in that group.
      </p>
      <ul>
        <li><p>
          Optionally, connect this mode's output to a ${stripRgthree(NodeTypesString.FAST_MUTER)}
          or ${stripRgthree(NodeTypesString.FAST_BYPASSER)} for a single toggle to quickly
          mute/bypass all its connected nodes.
        </p></li>
        <li><p>
          Optionally, connect a ${stripRgthree(NodeTypesString.NODE_MODE_RELAY)} to this nodes
          inputs to have it automatically toggle its mode. If connected, this will always take
          precedence (and disconnect any connected fast togglers).
        </p></li>
      </ul>
    `;
  }
}

app.registerExtension({
  name: "rgthree.NodeModeRepeater",
  registerCustomNodes() {
    addConnectionLayoutSupport(NodeModeRepeater, app, [
      ["Left", "Right"],
      ["Right", "Left"],
    ]);

    LiteGraph.registerNodeType(NodeModeRepeater.type, NodeModeRepeater);
    NodeModeRepeater.category = NodeModeRepeater._category;
  },
});
