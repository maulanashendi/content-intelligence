import { useEffect, useRef, useCallback } from "react"
import * as d3 from "d3"
import type { ClusterDetail } from "@ei-fe/api"

type Rec = "trending" | "worth_writing" | "saturated" | null

const REC_CONFIG: Record<string, { label: string; color: string; colorLight: string; colorDark: string }> = {
  trending: { label: "Trending", color: "#2EA868", colorLight: "#B6E8D4", colorDark: "#1B7249" },
  worth_writing: { label: "Worth Writing", color: "#4B63DC", colorLight: "#C5CEFF", colorDark: "#2E47B8" },
  saturated: { label: "Saturated", color: "#D9960A", colorLight: "#FFE5A0", colorDark: "#9B6A00" },
  unknown: { label: "Lainnya", color: "#7A7A8C", colorLight: "#D4D4DF", colorDark: "#4E4E5A" },
}

function recKey(rec: Rec): string {
  return rec ?? "unknown"
}

type NodeKind = "cluster" | "article"

interface GraphNode extends d3.SimulationNodeDatum {
  id: string
  kind: NodeKind
  label: string
  fullLabel: string
  recommendation: Rec
  clusterId: string
  color: string
  colorLight: string
  size: number
  sourceName?: string
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  linkType: "hub" | "peer"
  color: string
  strength: number
}

function buildGraph(
  details: ClusterDetail[],
  width: number,
  height: number,
): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = []
  const links: GraphLink[] = []

  const cols = Math.ceil(Math.sqrt(details.length))
  const rows = Math.ceil(details.length / cols)

  details.forEach((cluster, ci) => {
    const rk = recKey(cluster.recommendation)
    const cfg = REC_CONFIG[rk]!
    const col = ci % cols
    const row = Math.floor(ci / cols)
    const cx = width * ((col + 1) / (cols + 1))
    const cy = height * ((row + 1) / (rows + 1))

    nodes.push({
      id: `cluster-${cluster.id}`,
      kind: "cluster",
      label: cluster.label?.slice(0, 26) ?? cluster.id.slice(0, 8),
      fullLabel: cluster.label ?? "Tanpa label",
      recommendation: cluster.recommendation,
      clusterId: cluster.id,
      color: cfg.color,
      colorLight: cfg.colorLight,
      size: 26,
      x: cx,
      y: cy,
    })

    const articles = cluster.members.slice(0, 10)
    const articleNodes: GraphNode[] = articles.map((a) => {
      const size = 4 + (a.relevance_score ?? 0.5) * 5
      return {
        id: `article-${a.id}`,
        kind: "article",
        label: a.source_name,
        fullLabel: a.title,
        recommendation: cluster.recommendation,
        clusterId: cluster.id,
        color: cfg.color,
        colorLight: cfg.colorLight,
        sourceName: a.source_name,
        size,
        x: cx + (Math.random() - 0.5) * 70,
        y: cy + (Math.random() - 0.5) * 70,
      }
    })
    nodes.push(...articleNodes)

    articleNodes.forEach((an) => {
      links.push({
        source: `cluster-${cluster.id}`,
        target: an.id,
        linkType: "hub",
        color: cfg.color,
        strength: 0.5,
      })
    })

    // Peer links between articles in the same cluster
    const seen = new Set<string>()
    articleNodes.forEach((a, i) => {
      const numPeers = 1 + Math.floor(Math.random() * 2)
      let added = 0
      for (let j = 0; j < articleNodes.length && added < numPeers; j++) {
        const b = articleNodes[(i + j + 1) % articleNodes.length]!
        if (b.id === a.id) continue
        const key = [a.id, b.id].sort().join("|")
        if (!seen.has(key)) {
          seen.add(key)
          links.push({
            source: a.id,
            target: b.id,
            linkType: "peer",
            color: cfg.colorLight,
            strength: 0.12,
          })
          added++
        }
      }
    })
  })

  return { nodes, links }
}

interface ClusterForceGraphProps {
  details: ClusterDetail[]
  onClusterClick: (id: string) => void
}

const LEGEND: { rec: Rec; label: string }[] = [
  { rec: "trending", label: "Trending" },
  { rec: "worth_writing", label: "Worth Writing" },
  { rec: "saturated", label: "Saturated" },
]

export function ClusterForceGraph({ details, onClusterClick }: ClusterForceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const onClickRef = useRef(onClusterClick)
  const resetZoomRef = useRef<() => void>(() => {})

  useEffect(() => {
    onClickRef.current = onClusterClick
  }, [onClusterClick])

  useEffect(() => {
    const container = containerRef.current
    const svgEl = svgRef.current
    const tooltip = tooltipRef.current
    if (!container || !svgEl || !tooltip || details.length === 0) return

    const width = container.clientWidth
    const height = container.clientHeight
    const { nodes, links } = buildGraph(details, width, height)

    d3.select(svgEl).selectAll("*").remove()

    const svg = d3.select(svgEl)
    const g = svg.append("g")

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 5])
      .on("zoom", (event) => g.attr("transform", event.transform))
    svg.call(zoom)

    resetZoomRef.current = () =>
      svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity)

    const simulation = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance((d) => (d.linkType === "hub" ? 75 : 30))
          .strength((d) => d.strength),
      )
      .force("charge", d3.forceManyBody<GraphNode>().strength((d) => (d.kind === "cluster" ? -550 : -60)))
      .force("collide", d3.forceCollide<GraphNode>().radius((d) => d.size + 3))
      .force("cluster", (alpha) => {
        // Gently pull articles toward their cluster hub
        const clusterPos = new Map<string, { x: number; y: number }>()
        nodes.forEach((n) => {
          if (n.kind === "cluster") clusterPos.set(n.clusterId, { x: n.x ?? 0, y: n.y ?? 0 })
        })
        nodes.forEach((n) => {
          if (n.kind !== "article") return
          const pos = clusterPos.get(n.clusterId)
          if (!pos) return
          n.vx = (n.vx ?? 0) + (pos.x - (n.x ?? 0)) * 0.04 * alpha
          n.vy = (n.vy ?? 0) + (pos.y - (n.y ?? 0)) * 0.04 * alpha
        })
      })
      .force("boundary", () => {
        nodes.forEach((n) => {
          const m = n.size + 6
          n.x = Math.max(m, Math.min(width - m, n.x ?? width / 2))
          n.y = Math.max(m, Math.min(height - m, n.y ?? height / 2))
        })
      })

    // Draw peer links behind hub links
    const peerLink = g
      .append("g")
      .attr("class", "peer-links")
      .selectAll<SVGLineElement, GraphLink>("line")
      .data(links.filter((l) => l.linkType === "peer"))
      .join("line")
      .attr("stroke", (d) => d.color)
      .attr("stroke-opacity", 0.35)
      .attr("stroke-width", 0.8)

    const hubLink = g
      .append("g")
      .attr("class", "hub-links")
      .selectAll<SVGLineElement, GraphLink>("line")
      .data(links.filter((l) => l.linkType === "hub"))
      .join("line")
      .attr("stroke", (d) => d.color)
      .attr("stroke-opacity", 0.5)
      .attr("stroke-width", 1.4)

    const node = g
      .append("g")
      .selectAll<SVGGElement, GraphNode>("g")
      .data(nodes)
      .join("g")
      .style("cursor", (d) => (d.kind === "article" ? "default" : "pointer"))

    node
      .append("circle")
      .attr("r", (d) => d.size)
      .attr("fill", (d) => (d.kind === "cluster" ? d.color : d.colorLight))
      .attr("stroke", (d) => d.color)
      .attr("stroke-width", (d) => (d.kind === "cluster" ? 2.5 : 0.8))
      .attr("stroke-opacity", (d) => (d.kind === "article" ? 0.6 : 1))

    // Cluster label — two-line truncated text
    const clusterNodes = node.filter((d) => d.kind === "cluster")
    clusterNodes.each(function (d) {
      const el = d3.select(this)
      const words = d.label.split(" ")
      const mid = Math.ceil(words.length / 2)
      const line1 = words.slice(0, mid).join(" ")
      const line2 = words.slice(mid).join(" ")
      if (line2) {
        el.append("text")
          .text(line1)
          .attr("text-anchor", "middle")
          .attr("dy", "-0.5em")
          .attr("fill", "white")
          .attr("font-size", "9px")
          .attr("font-weight", "600")
          .style("pointer-events", "none")
          .style("font-family", "inherit")
        el.append("text")
          .text(line2)
          .attr("text-anchor", "middle")
          .attr("dy", "0.7em")
          .attr("fill", "white")
          .attr("font-size", "9px")
          .attr("font-weight", "600")
          .style("pointer-events", "none")
          .style("font-family", "inherit")
      } else {
        el.append("text")
          .text(line1)
          .attr("text-anchor", "middle")
          .attr("dy", "0.35em")
          .attr("fill", "white")
          .attr("font-size", "9px")
          .attr("font-weight", "600")
          .style("pointer-events", "none")
          .style("font-family", "inherit")
      }
    })

    let selectedClusterId: string | null = null

    node
      .on("mouseenter", function (event, d) {
        const rect = container.getBoundingClientRect()
        tooltip.style.opacity = "1"
        const recLabel = REC_CONFIG[recKey(d.recommendation)]!.label
        if (d.kind === "cluster") {
          tooltip.innerHTML = `<div style="font-weight:600;margin-bottom:3px">${d.fullLabel}</div><div style="font-size:11px;opacity:0.6">${recLabel}</div>`
        } else {
          tooltip.innerHTML = `<div style="font-weight:500;margin-bottom:3px;line-height:1.35">${d.fullLabel}</div><div style="font-size:11px;opacity:0.6">${d.sourceName ?? ""}</div>`
        }
        const tx = event.clientX - rect.left + 14
        const ty = event.clientY - rect.top + 14
        tooltip.style.left = Math.min(tx, rect.width - 250) + "px"
        tooltip.style.top = Math.min(ty, rect.height - 80) + "px"
      })
      .on("mousemove", function (event) {
        const rect = container.getBoundingClientRect()
        const tx = event.clientX - rect.left + 14
        const ty = event.clientY - rect.top + 14
        tooltip.style.left = Math.min(tx, rect.width - 250) + "px"
        tooltip.style.top = Math.min(ty, rect.height - 80) + "px"
      })
      .on("mouseleave", function () {
        tooltip.style.opacity = "0"
      })
      .on("click", function (event, d) {
        event.stopPropagation()
        if (d.kind !== "cluster") return
        if (selectedClusterId === d.clusterId) {
          selectedClusterId = null
          resetHighlight()
        } else {
          selectedClusterId = d.clusterId
          highlightCluster(d.clusterId)
          onClickRef.current(d.clusterId)
        }
      })

    svg.on("click", () => {
      selectedClusterId = null
      resetHighlight()
    })

    function highlightCluster(clusterId: string) {
      node
        .selectAll("circle")
        .attr("opacity", (d) => {
          const n = d as GraphNode
          return n.clusterId === clusterId ? 1 : 0.12
        })
      node
        .selectAll("text")
        .attr("opacity", (d) => {
          const n = d as GraphNode
          return n.clusterId === clusterId ? 1 : 0.12
        })
      hubLink.attr("stroke-opacity", (l) => {
        const src = typeof l.source === "object" ? (l.source as GraphNode) : null
        return src?.clusterId === clusterId ? 0.9 : 0.04
      })
      peerLink.attr("stroke-opacity", (l) => {
        const src = typeof l.source === "object" ? (l.source as GraphNode) : null
        return src?.clusterId === clusterId ? 0.7 : 0.04
      })
    }

    function resetHighlight() {
      node.selectAll("circle").attr("opacity", 1)
      node.selectAll("text").attr("opacity", 1)
      hubLink.attr("stroke-opacity", 0.5)
      peerLink.attr("stroke-opacity", 0.35)
    }

    const drag = d3
      .drag<SVGGElement, GraphNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on("drag", (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    node.call(drag)

    simulation.on("tick", () => {
      hubLink
        .attr("x1", (d) => (d.source as GraphNode).x ?? 0)
        .attr("y1", (d) => (d.source as GraphNode).y ?? 0)
        .attr("x2", (d) => (d.target as GraphNode).x ?? 0)
        .attr("y2", (d) => (d.target as GraphNode).y ?? 0)
      peerLink
        .attr("x1", (d) => (d.source as GraphNode).x ?? 0)
        .attr("y1", (d) => (d.source as GraphNode).y ?? 0)
        .attr("x2", (d) => (d.target as GraphNode).x ?? 0)
        .attr("y2", (d) => (d.target as GraphNode).y ?? 0)
      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => {
      simulation.stop()
      d3.select(svgEl).selectAll("*").remove()
    }
  }, [details])

  const handleReset = useCallback(() => {
    resetZoomRef.current()
  }, [])

  const totalArticles = details.reduce((s, d) => s + d.members.slice(0, 10).length, 0)
  const presentRecs = LEGEND.filter((item) => details.some((d) => d.recommendation === item.rec))

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Topic cluster map</span>
        <div style={{ display: "flex", gap: 14, marginLeft: 12, flexWrap: "wrap" }}>
          {presentRecs.map(({ rec, label }) => (
            <div key={rec} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11.5 }}>
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: REC_CONFIG[recKey(rec)]!.color,
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              <span style={{ color: "var(--fg-muted)" }}>{label}</span>
            </div>
          ))}
        </div>
        <span className="card-meta" style={{ marginLeft: "auto" }}>
          {details.length} kluster · {totalArticles} artikel · hover &amp; drag
        </span>
        <button className="btn btn-ghost" onClick={handleReset} style={{ padding: "3px 8px", fontSize: 11.5 }}>
          Reset zoom
        </button>
      </div>
      <div
        ref={containerRef}
        style={{ position: "relative", height: 500, background: "var(--bg-sunken)" }}
      >
        <svg ref={svgRef} width="100%" height="100%" />
        <div
          ref={tooltipRef}
          style={{
            position: "absolute",
            pointerEvents: "none",
            background: "var(--bg-elev)",
            border: "0.5px solid var(--line-strong)",
            borderRadius: "var(--radius)",
            padding: "8px 12px",
            fontSize: 12.5,
            maxWidth: 240,
            opacity: 0,
            transition: "opacity 0.1s",
            zIndex: 10,
            color: "var(--fg)",
            lineHeight: 1.4,
            boxShadow: "var(--shadow-md)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 10,
            left: 14,
            fontSize: 11,
            color: "var(--fg-faint)",
            fontFamily: "var(--font-mono)",
          }}
        >
          Klik kluster untuk highlight · Drag · Scroll to zoom
        </div>
      </div>
    </div>
  )
}
