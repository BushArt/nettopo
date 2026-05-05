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
  let nodeSelection;

  // ── Initialization ───────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    initializeGraph();
    setupEventListeners();
  });

  function initializeGraph() {
    const container = document.getElementById("graph-container");
    const W = container.clientWidth;
    const H = container.clientHeight;

    svg = d3.select("#graph")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");

    // D3 Force Simulation
    simulation = d3.forceSimulation(nodes)
      .force("charge", d3.forceManyBody().strength(-400))
      .force("collide", d3.forceCollide().radius(d => getNodeRadius(d) + 20))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .alphaDecay(0.02)
      .on("tick", ticked);

    // Stop simulation until first host arrives
    simulation.stop();

    setStatus("Waiting for scan start");

    // Handle window resize
    window.addEventListener('resize', () => {
      const newW = container.clientWidth;
      const newH = container.clientHeight;
      svg.attr("viewBox", `0 0 ${newW} ${newH}`);
      simulation.force("center", d3.forceCenter(newW / 2, newH / 2));
      simulation.alpha(0.3).restart();
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
      svg.selectAll("g.node").remove();
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
    nodes.push(host);

    // Update simulation
    simulation.nodes(nodes);

    // D3 data join
    nodeSelection = svg.selectAll("g.node")
      .data(nodes, d => d.ip); // Join by IP (primary key)

    // Enter new nodes
    const entering = nodeSelection.enter()
      .append("g")
        .attr("class", "node")
        .attr("transform", d => `translate(${d.x}, ${d.y})`)
        .on("click", (event, d) => console.log("Host detail:", d));

    // Add circle with pulse animation
    entering.append("circle")
      .attr("r", d => getNodeRadius(d))
      .attr("fill", d => OS_COLORS[d.os_family])
      .attr("stroke", NODE_STROKE)
      .attr("stroke-width", 2)
      .append("title")
        .text(d => tooltipText(d));

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
    svg.selectAll("g.node")
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