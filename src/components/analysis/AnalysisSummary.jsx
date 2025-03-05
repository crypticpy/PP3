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