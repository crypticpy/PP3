import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Container, 
  Paper, 
  Typography, 
  Grid, 
  Chip, 
  Divider, 
  Box, 
  Tab, 
  Tabs, 
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Alert
} from '@mui/material';
import { 
  CalendarToday, 
  Person, 
  Description, 
  Timeline, 
  HowToVote,
  Analytics
} from '@mui/icons-material';
import AnalysisSummary from '../analysis/AnalysisSummary';
import apiService from '../../services/api';

// TabPanel component for tab content
function TabPanel(props) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`bill-tabpanel-${index}`}
      aria-labelledby={`bill-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const BillDetail = () => {
  const { billId } = useParams();
  const [bill, setBill] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tabValue, setTabValue] = useState(0);

  // Fetch bill details
  useEffect(() => {
    const fetchBillDetails = async () => {
      try {
        setLoading(true);
        const data = await apiService.getBillDetails(billId);
        setBill(data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching bill details:', err);
        setError(err.message);
        setLoading(false);
      }
    };

    fetchBillDetails();
  }, [billId]);

  // Fetch bill analysis
  useEffect(() => {
    const fetchBillAnalysis = async () => {
      try {
        setAnalysisLoading(true);
        const data = await apiService.getBillAnalysis(billId);
        setAnalysis(data);
        setAnalysisLoading(false);
      } catch (err) {
        console.error('Error fetching bill analysis:', err);
        setAnalysis(null);
        setAnalysisLoading(false);
      }
    };

    if (billId) {
      fetchBillAnalysis();
    }
  }, [billId]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  if (loading) {
    return (
      <Container sx={{ mt: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert severity="error">Error: {error}</Alert>
      </Container>
    );
  }

  if (!bill) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert severity="info">Bill not found</Alert>
      </Container>
    );
  }

  return (
    <Container sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Chip 
                label={bill.state} 
                color="primary" 
                size="small" 
                sx={{ mr: 1 }} 
              />
              <Chip 
                label={bill.bill_number} 
                variant="outlined" 
                size="small" 
                sx={{ mr: 1 }} 
              />
              <Chip 
                label={bill.status} 
                color="secondary" 
                size="small" 
                variant="outlined" 
              />
            </Box>
            <Typography variant="h4" component="h1" gutterBottom>
              {bill.title}
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <CalendarToday fontSize="small" sx={{ mr: 1 }} />
              <Typography variant="body2">
                Last Action: {bill.last_action_date} - {bill.last_action}
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="body1" paragraph>
              {bill.description}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      <Box sx={{ width: '100%' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange} 
            aria-label="bill details tabs"
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab icon={<Description />} iconPosition="start" label="Text" />
            <Tab icon={<Person />} iconPosition="start" label="Sponsors" />
            <Tab icon={<Timeline />} iconPosition="start" label="History" />
            <Tab icon={<HowToVote />} iconPosition="start" label="Votes" />
            <Tab icon={<Analytics />} iconPosition="start" label="Analysis" />
          </Tabs>
        </Box>

        {/* Bill Text Tab */}
        <TabPanel value={tabValue} index={0}>
          <Paper elevation={1} sx={{ p: 3, maxHeight: '500px', overflow: 'auto' }}>
            {bill.text ? (
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                {bill.text}
              </Typography>
            ) : (
              <Alert severity="info">Bill text not available</Alert>
            )}
          </Paper>
        </TabPanel>

        {/* Sponsors Tab */}
        <TabPanel value={tabValue} index={1}>
          <Paper elevation={1} sx={{ p: 3 }}>
            {bill.sponsors && bill.sponsors.length > 0 ? (
              <List>
                {bill.sponsors.map((sponsor, index) => (
                  <ListItem key={index} divider={index < bill.sponsors.length - 1}>
                    <ListItemText primary={sponsor} />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Alert severity="info">No sponsor information available</Alert>
            )}
          </Paper>
        </TabPanel>

        {/* History Tab */}
        <TabPanel value={tabValue} index={2}>
          <Paper elevation={1} sx={{ p: 3 }}>
            {bill.history && bill.history.length > 0 ? (
              <List>
                {bill.history.map((event, index) => (
                  <ListItem key={index} divider={index < bill.history.length - 1}>
                    <ListItemText 
                      primary={event.action} 
                      secondary={event.date}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Alert severity="info">No history information available</Alert>
            )}
          </Paper>
        </TabPanel>

        {/* Votes Tab */}
        <TabPanel value={tabValue} index={3}>
          <Paper elevation={1} sx={{ p: 3 }}>
            {bill.votes && bill.votes.length > 0 ? (
              <List>
                {bill.votes.map((vote, index) => (
                  <ListItem key={index} divider={index < bill.votes.length - 1}>
                    <ListItemText 
                      primary={`${vote.chamber} Vote on ${vote.date}`} 
                      secondary={`Yes: ${vote.yes_count}, No: ${vote.no_count}, NV: ${vote.nv_count}`}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Alert severity="info">No voting information available</Alert>
            )}
          </Paper>
        </TabPanel>

        {/* Analysis Tab */}
        <TabPanel value={tabValue} index={4}>
          <AnalysisSummary analysis={analysis} loading={analysisLoading} />
        </TabPanel>
      </Box>
    </Container>
  );
};

export default BillDetail; 