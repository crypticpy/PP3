// visualizationService.js
import * as d3 from 'd3';

/**
 * Prepares data for a word cloud visualization
 * @param {Object} analysisData - The analysis data from the API
 * @returns {Array} - Data formatted for react-d3-cloud
 */
export const prepareWordCloudData = (analysisData) => {
  if (!analysisData || !analysisData.key_terms) {
    return [];
  }

  // For react-d3-cloud, we need an array of {text, value} objects
  return analysisData.key_terms.map(term => ({
    text: term.term,
    value: term.score * 100 // Scale the value appropriately
  }));
};

/**
 * Prepares data for a timeline visualization
 * @param {Object} billData - The bill data from the API
 * @returns {Array} - Data formatted for timeline visualization
 */
export const prepareTimelineData = (billData) => {
  if (!billData || !billData.history) {
    return [];
  }

  return billData.history.map(event => ({
    date: new Date(event.date),
    title: event.action,
    description: event.description || '',
    icon: determineIcon(event.action)
  }));
};

/**
 * Determines the appropriate icon for a timeline event
 * @param {string} action - The action text
 * @returns {string} - Icon identifier
 */
const determineIcon = (action) => {
  const actionLower = action.toLowerCase();

  if (actionLower.includes('introduced') || actionLower.includes('filed')) {
    return 'new';
  } else if (actionLower.includes('committee')) {
    return 'committee';
  } else if (actionLower.includes('passed') || actionLower.includes('approved')) {
    return 'passed';
  } else if (actionLower.includes('signed')) {
    return 'signed';
  } else if (actionLower.includes('vetoed')) {
    return 'vetoed';
  } else {
    return 'default';
  }
};

/**
 * Prepares data for impact assessment visualization
 * @param {Object} analysisData - The analysis data from the API
 * @returns {Array} - Data formatted for radar/spider chart
 */
export const prepareImpactData = (analysisData) => {
  if (!analysisData || !analysisData.impact_assessment) {
    return [];
  }

  // Convert impact assessment object to array format for visualization
  return Object.entries(analysisData.impact_assessment).map(([category, value]) => ({
    category: formatCategoryName(category),
    value: value
  }));
};

/**
 * Formats a category name for display (converts snake_case to Title Case)
 * @param {string} category - The category name in snake_case
 * @returns {string} - Formatted category name
 */
const formatCategoryName = (category) => {
  return category
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Prepares colors for visualization based on impact levels
 * @param {Array} data - The prepared impact data
 * @returns {Object} - Color configuration for visualizations
 */
export const getImpactColors = (data) => {
  const colorScale = d3.scaleLinear()
    .domain([0, 50, 100])
    .range(['#4caf50', '#ff9800', '#f44336']);

  return {
    scale: colorScale,
    byCategory: Object.fromEntries(
      data.map(item => [item.category, colorScale(item.value)])
    )
  };
};

export default {
  prepareWordCloudData,
  prepareTimelineData,
  prepareImpactData,
  getImpactColors
};