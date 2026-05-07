/**
 * graph.js — Phase 2 Live Force Simulation Renderer
 *
 * Receives host_discovered events from WebSocket client, renders nodes
 * in D3 force simulation dynamically as they arrive.
 */

(function () {
  "use strict";

  // Configuration
  const NODE_MIN_RADIUS  = 12;
  const NODE_MAX_RADIUS  = 40;
  const NODE_STROKE      = "#ffffff";
  const LABEL_OFFSET     = 14;

  // OS family colour mapping
  const OS_COLORS = {
    "Linux":     "#58A6FF",
    "Windows":   "#8B949E",
    "Network":   "#D29922",
    "Unknown":   "#A371F7",
    null:        "#A371F7",
    undefined:   "#A371F7"
  };

  // State
  const nodes = [];
  let simulation;
  let svg;
  let zoomLayer;
  let nodeSelection;
  let W;
  let H;
  let zoom;

  // ── Initialization ───────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    initializeGraph();
    setupEventListeners();
  });

  function initializeGraph() {
    svg = d3.select("#graph")
      .attr("width", "100%")
      .attr("height", "100%");

    const rect = svg.node().getBoundingClientRect();
    W = rect.width;
    H = rect.height;

    // Zoom pan group
    zoomLayer = svg.append("g").attr("id", "zoom-layer");

    // Zoom behaviour
    zoom = d3.zoom()
      .scaleExtent([0.3, 4])
      .on("zoom", (event) => {
        zoomLayer.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Double click reset view
    svg.on("dblclick.zoom", () => {
      // Reset all nodes to centre with small jitter
      nodes.forEach(host => {
        host.x = (W / 2) + (Math.random() - 0.5) * 60;
        host.y = (H / 2) + (Math.random() - 0.5) * 60;
      });

      // Reset zoom transform
      svg.transition().duration(400).call(
        zoom.transform,
        d3.zoomIdentity
      );

      // Restart simulation
      simulation.alpha(1).restart();
    });

    // D3 Force Simulation
    simulation = d3.forceSimulation(nodes)
      .force("charge", d3.forceManyBody().strength(d => {
        const base = Math.max(-60, -1200 / Math.max(1, nodes.length));
        return base * (0.88 + Math.random() * 0.24);
      }))
      .force("collide", d3.forceCollide().radius(d => getNodeRadius(d) + Math.max(1, 20 - nodes.length)))
      .force("x", d3.forceX(W / 2).strength(0.05))
      .force("y", d3.forceY(H / 2).strength(0.05))
      .alphaDecay(0.02)
      .velocityDecay(0.7)
      .on("tick", ticked);

    // Stop simulation until first host arrives
    simulation.stop();

    setStatus("Waiting for scan start");

    // Handle window resize
    window.addEventListener('resize', () => {
      const rect = svg.node().getBoundingClientRect();
      const newW = rect.width;
      const newH = rect.height;

      // Only restart simulation if resize is significant
      if (Math.abs(newW - W) > 50 || Math.abs(newH - H) > 50) {
        W = newW;
        H = newH;
        simulation.force("x", d3.forceX(W / 2).strength(0.05));
        simulation.force("y", d3.forceY(H / 2).strength(0.05));
        simulation.alpha(0.1).restart();
      }
    });
  }

  function setupEventListeners() {
    NetTopoClient.on('connected', () => {
      console.log('[Graph] Connected to WebSocket server');
      setStatus("Connected");
    });

    NetTopoClient.on('disconnected', () => {
      console.log('[Graph] Disconnected');
      setStatus("Disconnected — reconnecting...");
    });

    NetTopoClient.on('scan_started', (event) => {
      console.log('[Graph] Scan started', event);
      setStatus(`Scanning ${event.subnet}...`);
      // Clear existing nodes on new scan
      nodes.length = 0;
      zoomLayer.selectAll("g.node").remove();
      simulation.nodes(nodes);
    });

    NetTopoClient.on('host_discovered', (event) => {
      console.log('[Graph] Host discovered', event.data.ip);
      addNode(event.data);
    });

    NetTopoClient.on('scan_progress', (event) => {
      setStatus(`${event.hosts_found} hosts found · ${event.elapsed_s}s elapsed`);
    });

    NetTopoClient.on('scan_complete', (event) => {
      console.log('[Graph] Scan complete', event);
      setStatus(`Scan complete · ${event.total_hosts} hosts found · ${event.duration_s}s`);
      document.getElementById("scan-time").textContent = 
        "Completed: " + new Date().toISOString().replace("T", " ").replace("Z", " UTC");

    });

    NetTopoClient.on('scan_error', (event) => {
      console.error('[Graph] Scan error', event);
      setStatus(`Error: ${event.message}`);
    });
  }

  // ── Node Management ─────────────────────────────────────────────────────────

  function addNode(host) {
    // Initial position centre +-30px jitter, preserve if already set
    if (host.x === undefined) {
      host.x = (W / 2) + (Math.random() - 0.5) * 60;
      host.y = (H / 2) + (Math.random() - 0.5) * 60;
    }

    nodes.push(host);

    // Update simulation
    simulation.nodes(nodes);
    simulation.force("collide", d3.forceCollide().radius(d => getNodeRadius(d) + Math.max(1, 20 - nodes.length)));

    // D3 data join
    nodeSelection = zoomLayer.selectAll("g.node")
      .data(nodes, d => d.ip); // Join by IP (primary key)

    // Enter new nodes
    const entering = nodeSelection.enter()
      .append("g")
        .attr("class", "node")
        .attr("transform", d => `translate(${d.x}, ${d.y})`)
        .style("cursor", "default")
        .on("click", (event, d) => console.log("Host detail:", d));

    // Add circle with pulse animation
    const circle = entering.append("circle")
      .attr("r", 0)
      .attr("fill", d => OS_COLORS[d.os_family])
      .attr("stroke", NODE_STROKE)
      .attr("stroke-width", 2);

    circle.append("title")
      .text(d => tooltipText(d));

    circle.transition()
      .duration(600)
      .ease(d3.easeElasticOut)
      .attr("r", d => getNodeRadius(d));

    // Add IP label
    entering.append("text")
      .attr("dy", d => getNodeRadius(d) + LABEL_OFFSET)
      .attr("font-size", "11px")
      .attr("font-family", "JetBrains Mono, Fira Code, monospace")
      .attr("text-anchor", "middle")
      .attr("fill", "#E6EDF3")
      .text(d => d.ip);

    // Add port count badge
    entering.filter(d => d.ports && d.ports.length > 0)
      .append("text")
        .attr("dy", d => -getNodeRadius(d) - 4)
        .attr("font-size", "9px")
        .attr("fill", "#8B949E")
        .attr("text-anchor", "middle")
        .text(d => `${d.ports.length}p`);

    // Restart simulation with full energy
    simulation.alpha(1).restart();
  }

  function ticked() {
    zoomLayer.selectAll("g.node")
      .attr("transform", d => `translate(${d.x}, ${d.y})`);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function getNodeRadius(host) {
    const portCount = host.ports ? host.ports.length : 0;
    return Math.min(NODE_MIN_RADIUS + (3 * portCount), NODE_MAX_RADIUS);
  }

  function tooltipText(host) {
    const lines = [
      `IP: ${host.ip}`,
      host.hostname ? `Host: ${host.hostname}` : null,
      host.os_detail ? `OS: ${host.os_detail}` : null,
      host.mac       ? `MAC: ${host.mac}`       : null,
      host.vendor    ? `Vendor: ${host.vendor}`  : null,
      `Open ports: ${host.ports ? host.ports.length : 0}`,
    ].filter(Boolean);

    if (host.ports && host.ports.length > 0) {
      lines.push("─".repeat(24));
      host.ports.slice(0, 10).forEach(p => {
        lines.push(`${p.port}/${p.proto}  ${p.service || ""}  ${p.version || ""}`);
      });
      if (host.ports.length > 10) {
        lines.push(`… and ${host.ports.length - 10} more`);
      }
    }
    return lines.join("\n");
  }

  function setStatus(msg) {
    const el = document.getElementById("status");
    if (el) el.textContent = msg;
  }

  function showError() {
    const el = document.getElementById("error-state");
    if (el) el.style.display = "block";
  }

})();