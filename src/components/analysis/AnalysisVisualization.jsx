import React from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Grid,
  LinearProgress,
  Divider
} from '@mui/material';
import { 
  ThumbUp, 
  ThumbDown, 
  QuestionMark,
  TrendingUp,
  TrendingDown,
  TrendingFlat
} from '@mui/icons-material';

/**
 * Component to visualize bill analysis data
 * 
 * @param {Object} analysis - The analysis data object
 * @returns {JSX.Element} - The rendered component
 */
const AnalysisVisualization = ({ analysis }) => {
  if (!analysis) {
    return null;
  }

  // Convert sentiment score (-1 to 1) to percentage (0 to 100)
  const sentimentPercentage = ((analysis.sentiment + 1) / 2) * 100;
  
  // Determine sentiment category and icon
  const getSentimentCategory = () => {
    if (analysis.sentiment > 0.2) return { label: 'Positive', icon: <ThumbUp color="success" />, color: 'success.main' };
    if (analysis.sentiment < -0.2) return { label: 'Negative', icon: <ThumbDown color="error" />, color: 'error.main' };
    return { label: 'Neutral', icon: <QuestionMark color="warning" />, color: 'warning.main' };
  };

  const sentimentCategory = getSentimentCategory();

  // Helper function to get impact icon
  const getImpactIcon = (text) => {
    const lowerText = text.toLowerCase();
    if (lowerText.includes('increase') || lowerText.includes('improve') || lowerText.includes('enhance')) {
      return <TrendingUp color="success" />;
    } else if (lowerText.includes('decrease') || lowerText.includes('reduce') || lowerText.includes('limit')) {
      return <TrendingDown color="error" />;
    }
    return <TrendingFlat color="info" />;
  };

  return (
    <Grid container spacing={3}>
      {/* Sentiment Analysis Card */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Sentiment Analysis
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              {sentimentCategory.icon}
              <Typography variant="body1" sx={{ ml: 1 }}>
                {sentimentCategory.label} ({analysis.sentiment.toFixed(2)})
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 3 }}>
              <Box sx={{ width: '100%', mr: 1 }}>
                <LinearProgress 
                  variant="determinate" 
                  value={sentimentPercentage} 
                  color={sentimentCategory.label.toLowerCase()} 
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
              <Box sx={{ minWidth: 35 }}>
                <Typography variant="body2" color="text.secondary">
                  {Math.round(sentimentPercentage)}%
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Key Points Card */}
      <Grid item xs={12} md={6}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Key Points
            </Typography>
            {analysis.key_points && analysis.key_points.length > 0 ? (
              <Box component="ul" sx={{ pl: 2 }}>
                {analysis.key_points.map((point, index) => (
                  <Box component="li" key={index} sx={{ mb: 1 }}>
                    <Typography variant="body2">{point}</Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No key points available
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Potential Impacts Card */}
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Potential Impacts
            </Typography>
            <Divider sx={{ mb: 2 }} />
            {analysis.potential_impacts ? (
              <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                {getImpactIcon(analysis.potential_impacts)}
                <Typography variant="body2" sx={{ ml: 1 }}>
                  {analysis.potential_impacts}
                </Typography>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No impact analysis available
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default AnalysisVisualization; 