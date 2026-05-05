/**
 * graph.js — Phase 1 Static Graph Renderer
 *
 * Fetches data/sessions/latest.json and renders one SVG circle per host
 * in a grid layout. No force simulation yet — that is Phase 2.
 *
 * Phase 2 changes are documented inline so the upgrade path is clear.
 */

(function () {
  "use strict";

  const DATA_URL = "../data/sessions/latest.json";
  const NODE_RADIUS = 20;          // Phase 2: becomes 12 + (3 * open_port_count), max 40
  const NODE_FILL   = "#4A90D9";   // Phase 2: becomes OS-family color mapping
  const NODE_STROKE = "#ffffff";   // Phase 2: becomes risk-level color
  const LABEL_OFFSET = NODE_RADIUS + 14;

  // ── Fetch and render ───────────────────────────────────────────────────────

  fetch(DATA_URL)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(hosts => {
      if (!Array.isArray(hosts) || hosts.length === 0) {
        showError();
        setStatus("No hosts found in latest scan.");
        return;
      }
      renderGraph(hosts);
      setStatus(`${hosts.length} host${hosts.length !== 1 ? "s" : ""} · scan complete`);
      if (hosts[0] && hosts[0].scan_time) {
        document.getElementById("scan-time").textContent =
          "Scanned: " + hosts[0].scan_time.replace("T", " ").replace("Z", " UTC");
      }
    })
    .catch(err => {
      showError();
      setStatus("Failed to load scan data — " + err.message);
      console.error("NetTopo fetch error:", err);
    });

  // ── Graph rendering ────────────────────────────────────────────────────────

  function renderGraph(hosts) {
    const container = document.getElementById("graph-container");
    const W = container.clientWidth;
    const H = container.clientHeight;

    const svg = d3.select("#graph")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");

    // Grid layout: ceil(sqrt(n)) columns, evenly spaced
    // Phase 2: replaced entirely by D3 force simulation
    const cols  = Math.ceil(Math.sqrt(hosts.length));
    const cellW = W / (cols + 1);
    const cellH = H / (Math.ceil(hosts.length / cols) + 1);

    const positions = hosts.map((_, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      return {
        x: cellW * (col + 1),
        y: cellH * (row + 1),
      };
    });

    // Bind data — one <g class="node"> per host
    const nodes = svg.selectAll("g.node")
      .data(hosts)
      .enter()
      .append("g")
        .attr("class", "node")
        .attr("transform", (_, i) => `translate(${positions[i].x}, ${positions[i].y})`)
        .on("click", (event, d) => {
          // Phase 2: opens right detail panel
          console.log("Host detail:", d);
        });

    // Circle
    nodes.append("circle")
      .attr("r", NODE_RADIUS)
      .attr("fill", NODE_FILL)    // Phase 2: osColor(d.os_family)
      .attr("stroke", NODE_STROKE) // Phase 2: riskColor(d.risk_level)
      .attr("stroke-width", 2)
      .append("title")             // native browser tooltip — Phase 2: replaced by floating div
        .text(d => tooltipText(d));

    // IP label below node
    nodes.append("text")
      .attr("dy", LABEL_OFFSET)
      .text(d => d.ip);           // Phase 2: short hostname + last octet fallback

    // Open port count badge (useful even in Phase 1)
    nodes.filter(d => d.ports && d.ports.length > 0)
      .append("text")
        .attr("dy", -NODE_RADIUS - 4)
        .attr("font-size", "9px")
        .attr("fill", "#8B949E")
        .text(d => `${d.ports.length}p`);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

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
