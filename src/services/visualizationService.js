
/**
 * Visualization Service
 * 
 * This service contains utility functions for data transformation and preparation
 * for various data visualizations used in the application.
 */

/**
 * Prepare data for word cloud visualization from bill analysis
 * 
 * @param {Object} analysis - Analysis data containing key terms
 * @returns {Array} - Formatted data for react-d3-cloud
 */
export const prepareWordCloudData = (analysis) => {
  // Handle case when analysis is undefined or doesn't have key_terms
  if (!analysis || !analysis.key_terms) {
    return [];
  }

  let terms = [];

  // Handle different possible formats of key_terms
  if (Array.isArray(analysis.key_terms)) {
    // If key_terms is already an array of objects with text/value properties
    if (analysis.key_terms.length > 0 && typeof analysis.key_terms[0] === 'object') {
      terms = analysis.key_terms.map(term => ({
        text: term.text || term.term || term.word || '',
        value: term.value || term.weight || term.score || term.frequency || 1
      }));
    } 
    // If key_terms is an array of strings
    else if (analysis.key_terms.length > 0 && typeof analysis.key_terms[0] === 'string') {
      terms = analysis.key_terms.map((term, index) => ({
        text: term,
        value: 100 - (index * 5) // Assign decreasing importance based on array position
      }));
    }
  } 
  // If key_terms is an object with term:score pairs
  else if (typeof analysis.key_terms === 'object') {
    terms = Object.entries(analysis.key_terms).map(([term, value]) => ({
      text: term,
      value: typeof value === 'number' ? value : 1
    }));
  }

  // Filter out any empty text values and sort by value
  return terms
    .filter(term => term.text && term.text.trim() !== '')
    .sort((a, b) => b.value - a.value)
    .slice(0, 100); // Limit to top 100 terms for performance
};

/**
 * Prepare data for timeline visualization
 * 
 * @param {Object} bill - Bill data containing history/events
 * @returns {Array} - Formatted timeline data
 */
export const prepareTimelineData = (bill) => {
  if (!bill || (!bill.history && !bill.events)) {
    return [];
  }

  const events = bill.history || bill.events || [];
  
  return events.map((event, index) => ({
    id: index,
    date: new Date(event.date),
    title: event.action || event.title || 'Event',
    description: event.description || event.action || '',
    icon: getEventIcon(event),
    category: getEventCategory(event)
  })).sort((a, b) => a.date - b.date);
};

/**
 * Helper function to determine appropriate icon for timeline event
 */
const getEventIcon = (event) => {
  const action = (event.action || '').toLowerCase();
  
  if (action.includes('introduc') || action.includes('filed')) {
    return 'CREATE';
  } else if (action.includes('committee') || action.includes('refer')) {
    return 'COMMITTEE';
  } else if (action.includes('pass') || action.includes('approve')) {
    return 'PASS';
  } else if (action.includes('fail') || action.includes('reject') || action.includes('veto')) {
    return 'FAIL';
  } else if (action.includes('amend')) {
    return 'AMENDMENT';
  } else if (action.includes('sign') && action.includes('governor')) {
    return 'SIGN';
  } else {
    return 'EVENT';
  }
};

/**
 * Helper function to categorize timeline events
 */
const getEventCategory = (event) => {
  const action = (event.action || '').toLowerCase();
  
  if (action.includes('house')) {
    return 'house';
  } else if (action.includes('senate')) {
    return 'senate';
  } else if (action.includes('governor') || action.includes('executive')) {
    return 'executive';
  } else if (action.includes('committee')) {
    return 'committee';
  } else {
    return 'other';
  }
};

/**
 * Format stakeholder data for network visualization
 */
export const prepareStakeholderData = (analysis) => {
  if (!analysis || !analysis.stakeholders) {
    return { nodes: [], links: [] };
  }

  const nodes = [];
  const links = [];
  const billNode = { id: 'bill', name: 'Bill', type: 'bill', value: 100 };
  nodes.push(billNode);

  // Process stakeholders
  if (Array.isArray(analysis.stakeholders)) {
    analysis.stakeholders.forEach((stakeholder, index) => {
      const id = `stakeholder-${index}`;
      const name = stakeholder.name || stakeholder.organization || `Stakeholder ${index + 1}`;
      const type = stakeholder.type || stakeholder.position || 'other';
      const impact = stakeholder.impact || stakeholder.stance || 'neutral';
      
      nodes.push({
        id,
        name,
        type,
        impact,
        value: 60
      });
      
      links.push({
        source: 'bill',
        target: id,
        value: 10,
        type: impact
      });
    });
  }

  return { nodes, links };
};

export default {
  prepareWordCloudData,
  prepareTimelineData,
  prepareStakeholderData
};
