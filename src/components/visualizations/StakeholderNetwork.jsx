import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { prepareNetworkData } from '../../services/visualizationService';

/**
 * Stakeholder Network Component
 * 
 * Displays a force-directed graph visualization of stakeholders and their relationships
 * 
 * @param {Object} analysis - The bill analysis data containing stakeholder information
 */
const StakeholderNetwork = ({ analysis }) => {
  const svgRef = useRef(null);
  const { nodes, links } = prepareNetworkData(analysis);
  
  useEffect(() => {
    if (!nodes.length) return;
    
    const width = svgRef.current.clientWidth;
    const height = 400;
    
    // Clear previous visualization
    d3.select(svgRef.current).selectAll("*").remove();
    
    const svg = d3.select(svgRef.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .attr("style", "max-width: 100%; height: auto;");
    
    // Define stakeholder groups and colors
    const groups = {
      'government': '#3b82f6',
      'industry': '#f59e0b',
      'advocacy': '#10b981',
      'public': '#8b5cf6',
      'other': '#6b7280'
    };
    
    // Create a tooltip
    const tooltip = d3.select("body")
      .append("div")
      .attr("class", "d3-tooltip")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background-color", "white")
      .style("border", "1px solid #ddd")
      .style("border-radius", "4px")
      .style("padding", "8px")
      .style("box-shadow", "0 2px 10px rgba(0,0,0,0.1)")
      .style("pointer-events", "none")
      .style("font-size", "12px");
    
    // Create the simulation
    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(d => Math.sqrt(d.value) * 5 + 10));
    
    // Create the links
    const link = svg.append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "#999")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", d => Math.sqrt(d.value));
    
    // Create the nodes
    const node = svg.append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", d => Math.sqrt(d.value) * 5 + 5)
      .attr("fill", d => groups[d.group] || groups.other)
      .call(drag(simulation))
      .on("mouseover", function(event, d) {
        tooltip
          .style("visibility", "visible")
          .html(`<strong>${d.id}</strong><br>Type: ${d.group}<br>Influence: ${d.value}`)
          .style("left", (event.pageX + 10) + "px")
          .style("top", (event.pageY - 10) + "px");
        d3.select(this).attr("stroke", "#000").attr("stroke-width", 2);
      })
      .on("mousemove", function(event) {
        tooltip
          .style("left", (event.pageX + 10) + "px")
          .style("top", (event.pageY - 10) + "px");
      })
      .on("mouseout", function() {
        tooltip.style("visibility", "hidden");
        d3.select(this).attr("stroke", null);
      });
    
    // Add labels to the nodes
    const label = svg.append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text(d => d.id)
      .attr("font-size", 10)
      .attr("dx", 12)
      .attr("dy", 4)
      .style("pointer-events", "none");
    
    // Update positions on each tick
    simulation.on("tick", () => {
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);
      
      node
        .attr("cx", d => d.x = Math.max(10, Math.min(width - 10, d.x)))
        .attr("cy", d => d.y = Math.max(10, Math.min(height - 10, d.y)));
      
      label
        .attr("x", d => d.x)
        .attr("y", d => d.y);
    });
    
    // Create a drag behavior
    function drag(simulation) {
      function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }
      
      function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }
      
      function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }
      
      return d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended);
    }
    
    // Create a legend
    const legend = svg.append("g")
      .attr("transform", `translate(20, 20)`);
    
    Object.entries(groups).forEach(([key, color], i) => {
      const legendRow = legend.append("g")
        .attr("transform", `translate(0, ${i * 20})`);
      
      legendRow.append("circle")
        .attr("r", 6)
        .attr("fill", color);
      
      legendRow.append("text")
        .attr("x", 15)
        .attr("y", 4)
        .text(key.charAt(0).toUpperCase() + key.slice(1))
        .style("font-size", "12px");
    });
    
    // Clean up on unmount
    return () => {
      tooltip.remove();
    };
  }, [nodes, links]);
  
  if (!nodes.length) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No stakeholder network data available.
      </div>
    );
  }

  return (
    <div className="stakeholder-network mt-4 bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
        Stakeholder Network Analysis
      </h3>
      <svg 
        ref={svgRef} 
        className="w-full" 
        style={{ minHeight: "400px" }}
      ></svg>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
        Network visualization of stakeholders and their relationships. 
        Node size indicates influence level.
      </p>
    </div>
  );
};

export default StakeholderNetwork; 