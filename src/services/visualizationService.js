/**
 * Utility functions for preparing data for visualizations
 */

/**
 * Prepares word frequency data for word cloud visualization
 * @param {Object} analysisData - Analysis data
 * @returns {Array} - Formatted data for word cloud visualization
 */
export const prepareWordCloudData = (analysisData) => {
  if (!analysisData || !analysisData.key_terms) {
    return [];
  }

  // Convert the key terms to the format expected by the word cloud
  return Object.entries(analysisData.key_terms).map(([text, value]) => ({
    text,
    value: typeof value === 'number' ? value : 1,
  }));
};

/**
 * Prepares impact data for visualization
 * @param {Object} analysisData - Raw analysis data
 * @returns {Object} - Formatted data for impact visualization
 */
export const prepareImpactData = (analysisData) => {
  if (!analysisData || !analysisData.impact_areas) {
    return { labels: [], values: [] };
  }

  const impactAreas = analysisData.impact_areas || {};

  // Convert impact areas to chart data format
  const labels = Object.keys(impactAreas);
  const values = labels.map(label => impactAreas[label]);

  return {
    labels,
    values,
  };
};

/**
 * Prepares sentiment data for visualization
 * @param {Object} analysisData - Raw analysis data
 * @returns {Object} - Formatted data for sentiment visualization
 */
export const prepareSentimentData = (analysisData) => {
  if (!analysisData || typeof analysisData.sentiment !== 'number') {
    return { value: 0, category: 'neutral' };
  }

  const sentiment = analysisData.sentiment;

  // Determine sentiment category
  let category = 'neutral';
  if (sentiment > 0.33) {
    category = 'positive';
  } else if (sentiment < -0.33) {
    category = 'negative';
  }

  return {
    value: sentiment,
    category,
    percentage: ((sentiment + 1) / 2) * 100, // Convert -1 to 1 scale to 0-100%
  };
};

/**
 * Prepares timeline data for bill progress visualization
 * @param {Object} billData - Bill data with history
 * @returns {Object} - Formatted data for timeline visualization
 */
export const prepareBillTimelineData = (billData) => {
  if (!billData || !billData.history) {
    return { dates: [], events: [] };
  }

  const history = billData.history || [];

  // Sort events chronologically
  const sortedEvents = [...history].sort((a, b) => {
    return new Date(a.date) - new Date(b.date);
  });

  return {
    dates: sortedEvents.map(event => event.date),
    events: sortedEvents.map(event => ({
      date: event.date,
      action: event.action,
      chamber: event.chamber,
      description: event.description,
    })),
  };
};

//import * as d3 from 'd3';

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


export default {
  prepareWordCloudData,
  prepareTimelineData,
  prepareImpactData,
  getImpactColors,
  prepareBillTimelineData,
  prepareSentimentData
};