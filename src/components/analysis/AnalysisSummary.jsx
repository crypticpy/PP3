import React, { useState } from 'react';
import { Card, CardContent, Typography, Box, Chip, CircularProgress, Tabs, Tab, Divider } from '@mui/material';
import { ThumbUp, ThumbDown, QuestionMark, Assessment, Article } from '@mui/icons-material';
import AnalysisVisualization from './AnalysisVisualization';

// TabPanel component for tab content
function TabPanel(props) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`analysis-tabpanel-${index}`}
      aria-labelledby={`analysis-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const AnalysisSummary = ({ analysis, loading }) => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', padding: 4 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (!analysis) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body1">No analysis available for this bill.</Typography>
        </CardContent>
      </Card>
    );
  }

  // Determine sentiment icon
  const getSentimentIcon = () => {
    if (analysis.sentiment > 0.2) return <ThumbUp color="success" />;
    if (analysis.sentiment < -0.2) return <ThumbDown color="error" />;
    return <QuestionMark color="warning" />;
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            AI Analysis Summary
          </Typography>
          <Chip 
            icon={getSentimentIcon()} 
            label={analysis.sentiment > 0.2 ? 'Positive' : analysis.sentiment < -0.2 ? 'Negative' : 'Neutral'} 
            color={analysis.sentiment > 0.2 ? 'success' : analysis.sentiment < -0.2 ? 'error' : 'warning'}
            variant="outlined"
          />
        </Box>
        
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange} 
            aria-label="analysis tabs"
          >
            <Tab icon={<Article />} iconPosition="start" label="Summary" />
            <Tab icon={<Assessment />} iconPosition="start" label="Visualization" />
          </Tabs>
        </Box>
        
        <TabPanel value={tabValue} index={0}>
          <Typography variant="body1" paragraph>
            {analysis.summary}
          </Typography>
          
          {analysis.key_points && analysis.key_points.length > 0 && (
            <>
              <Typography variant="subtitle1" sx={{ mt: 2, fontWeight: 'bold' }}>
                Key Points:
              </Typography>
              <ul>
                {analysis.key_points.map((point, index) => (
                  <li key={index}>
                    <Typography variant="body2">{point}</Typography>
                  </li>
                ))}
              </ul>
            </>
          )}
          
          {analysis.potential_impacts && (
            <>
              <Typography variant="subtitle1" sx={{ mt: 2, fontWeight: 'bold' }}>
                Potential Impacts:
              </Typography>
              <Typography variant="body2" paragraph>
                {analysis.potential_impacts}
              </Typography>
            </>
          )}
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          <AnalysisVisualization analysis={analysis} />
        </TabPanel>
      </CardContent>
    </Card>
  );
};

export default AnalysisSummary; 
import React, { useState, useEffect } from 'react';
import apiService from '../../services/apiService';

const AnalysisSummary = () => {
  const [analysisStats, setAnalysisStats] = useState({
    totalAnalyses: 0,
    highImpactCount: 0,
    recentAnalyses: [],
    categoryCounts: {}
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalysisStats = async () => {
      setLoading(true);
      try {
        // Ideally, we'd have a dedicated endpoint for analysis statistics
        // As a fallback, we'll fetch recent legislation and count analyses
        const legislationResponse = await apiService.get('/legislation?limit=20');
        
        if (legislationResponse && legislationResponse.items) {
          const items = legislationResponse.items;
          const withAnalysis = items.filter(item => item.latest_analysis || item.analyses?.length > 0);
          
          // Count by impact category if available
          const categories = {};
          const highImpact = [];
          
          withAnalysis.forEach(item => {
            const analysis = item.latest_analysis;
            if (analysis) {
              if (analysis.impact_category) {
                categories[analysis.impact_category] = (categories[analysis.impact_category] || 0) + 1;
              }
              
              if (analysis.impact_level === 'high' || analysis.impact_level === 'critical') {
                highImpact.push(item);
              }
            }
          });
          
          setAnalysisStats({
            totalAnalyses: withAnalysis.length,
            highImpactCount: highImpact.length,
            recentAnalyses: withAnalysis.slice(0, 3),
            categoryCounts: categories
          });
        }
      } catch (err) {
        console.error('Error fetching analysis statistics:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysisStats();
  }, []);

  if (loading) {
    return <div className="animate-pulse">Loading analysis data...</div>;
  }

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-blue-50 p-3 rounded text-center">
          <span className="block text-2xl font-bold text-blue-700">{analysisStats.totalAnalyses}</span>
          <span className="text-sm text-blue-800">Total Analyses</span>
        </div>
        <div className="bg-red-50 p-3 rounded text-center">
          <span className="block text-2xl font-bold text-red-700">{analysisStats.highImpactCount}</span>
          <span className="text-sm text-red-800">High Impact</span>
        </div>
      </div>

      {Object.keys(analysisStats.categoryCounts).length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold mb-2">Impact Categories</h3>
          <div className="space-y-2">
            {Object.entries(analysisStats.categoryCounts).map(([category, count]) => (
              <div key={category} className="flex items-center justify-between">
                <span className="text-sm">{category.replace('_', ' ')}</span>
                <span className="text-sm font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {analysisStats.recentAnalyses.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2">Recent Analyses</h3>
          <div className="space-y-2">
            {analysisStats.recentAnalyses.map((item, index) => (
              <div key={index} className="text-sm">
                <a href={`/legislation/${item.id}`} className="text-blue-600 hover:underline">
                  {item.bill_number}
                </a>
                {item.latest_analysis?.impact_level && (
                  <span className={`ml-2 px-1.5 py-0.5 rounded-full text-xs 
                    ${item.latest_analysis.impact_level === 'high' ? 'bg-orange-100 text-orange-800' :
                      item.latest_analysis.impact_level === 'critical' ? 'bg-red-100 text-red-800' :
                      item.latest_analysis.impact_level === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'}`}>
                    {item.latest_analysis.impact_level}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisSummary;
