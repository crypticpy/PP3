/**
 * Visualization Service
 * 
 * Provides utilities and data transformation functions for various
 * data visualizations throughout the application.
 */

/**
 * Transforms bill data into a format suitable for timeline visualization
 * @param {Object} bill - The bill data
 * @returns {Array} - Formatted data for timeline visualization
 */
export const prepareBillTimelineData = (bill) => {
  if (!bill || !bill.history) return [];
  
  return bill.history.map((event, index) => ({
    id: index,
    date: new Date(event.date),
    title: event.action,
    description: event.chamber || '',
    status: event.importance || 'normal'
  }));
};

/**
 * Transforms analysis data into a format suitable for word cloud visualization
 * @param {Object} analysis - The bill analysis data
 * @returns {Array} - Formatted data for word cloud
 */
export const prepareWordCloudData = (analysis) => {
  if (!analysis || !analysis.keyTerms) return [];
  
  return analysis.keyTerms.map(term => ({
    text: term.term,
    value: term.relevance * 100
  }));
};

/**
 * Prepares data for geographic impact visualization
 * @param {Object} analysis - The bill analysis data
 * @returns {Object} - Formatted data for geographic visualization
 */
export const prepareGeographicData = (analysis) => {
  if (!analysis || !analysis.regionalImpact) return {};
  
  return {
    regions: analysis.regionalImpact.map(region => ({
      id: region.region,
      value: region.impactScore,
      label: region.region,
      description: region.description
    }))
  };
};

/**
 * Transforms bill data for comparative analysis
 * @param {Array} bills - Array of similar bills
 * @returns {Array} - Formatted data for comparative visualization
 */
export const prepareComparativeData = (bills) => {
  if (!bills || !Array.isArray(bills)) return [];
  
  return bills.map(bill => ({
    id: bill.id,
    title: bill.title.substring(0, 30) + (bill.title.length > 30 ? '...' : ''),
    progress: bill.progress || 0,
    status: bill.status,
    support: bill.analysis?.support || 0,
    opposition: bill.analysis?.opposition || 0,
    introduced: new Date(bill.introduced_date)
  }));
};

/**
 * Prepares stakeholder network data
 * @param {Object} analysis - The bill analysis data
 * @returns {Object} - Nodes and links for network visualization
 */
export const prepareNetworkData = (analysis) => {
  if (!analysis || !analysis.stakeholders) return { nodes: [], links: [] };
  
  const nodes = analysis.stakeholders.map(stakeholder => ({
    id: stakeholder.name,
    group: stakeholder.type,
    value: stakeholder.influence
  }));
  
  const links = [];
  
  // Create links between stakeholders based on relationships
  if (analysis.stakeholderRelationships) {
    analysis.stakeholderRelationships.forEach(rel => {
      links.push({
        source: rel.source,
        target: rel.target,
        value: rel.strength
      });
    });
  }
  
  return { nodes, links };
};

/**
 * Prepares historical trend data
 * @param {Array} historicalData - Historical data for similar legislation
 * @returns {Array} - Formatted data for trend visualization
 */
export const prepareHistoricalTrendData = (historicalData) => {
  if (!historicalData || !Array.isArray(historicalData)) return [];
  
  return historicalData.map(point => ({
    date: new Date(point.date),
    passRate: point.passRate,
    count: point.count,
    averageTimeToPass: point.averageTimeToPass
  }));
}; 