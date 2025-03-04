"""
notification.py

Notification system for PolicyPulse that sends alerts to users about relevant legislation
based on their preferences and configured thresholds.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models import (
    User, AlertPreference, AlertHistory, Legislation,
    NotificationTypeEnum, LegislationPriority
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class NotificationManager:
    def __init__(self, db_session: Session, smtp_config: Dict = None):
        """
        Initialize the notification manager.
        
        Args:
            db_session: SQLAlchemy session for database access.
            smtp_config: Optional configuration for SMTP. If not provided, defaults to environment variables.
        """
        self.db_session = db_session
        self.smtp_config = smtp_config or {
            "server": os.environ.get("SMTP_SERVER", "smtp.example.com"),
            "port": int(os.environ.get("SMTP_PORT", "587")),
            "username": os.environ.get("SMTP_USERNAME", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "from_email": os.environ.get("SMTP_FROM", "notifications@policypulse.org"),
        }
    
    def process_pending_notifications(self) -> Dict[str, int]:
        """
        Process all pending notifications based on user preferences.
        
        Returns:
            A dictionary with statistics about the notifications processed.
        """
        stats = {
            "high_priority": 0,
            "new_bill": 0,
            "status_change": 0,
            "analysis_complete": 0,
            "errors": 0,
            "total": 0
        }
        
        # Retrieve users with active alert preferences
        users = self.db_session.query(User).join(
            AlertPreference,
            and_(
                User.id == AlertPreference.user_id,
                AlertPreference.active == True
            )
        ).all()
        
        for user in users:
            try:
                # Process new legislation alerts if enabled
                if user.alert_preferences.notify_on_new:
                    new_alerts = self._process_new_legislation_alerts(user)
                    stats["new_bill"] += new_alerts
                
                # Process analysis complete alerts if enabled
                if user.alert_preferences.notify_on_analysis:
                    analysis_alerts = self._process_analysis_alerts(user)
                    stats["analysis_complete"] += analysis_alerts
                
                # Process high priority alerts (always on)
                high_priority_alerts = self._process_high_priority_alerts(user)
                stats["high_priority"] += high_priority_alerts
                
                # Update total notifications sent
                stats["total"] += new_alerts + analysis_alerts + high_priority_alerts
                
            except Exception as e:
                logger.error(f"Error processing notifications for user {user.email}: {e}")
                stats["errors"] += 1
        
        return stats
    
    def _process_high_priority_alerts(self, user: User) -> int:
        """
        Process high priority legislation alerts for a user.
        
        Args:
            user: The user for whom to process alerts.
            
        Returns:
            Number of high priority notifications sent.
        """
        count = 0
        
        # Determine the threshold for high priority based on the user's preferences
        high_priority_threshold = user.alert_preferences.health_threshold
        recent_high_priority = self.db_session.query(Legislation).join(
            LegislationPriority,
            and_(
                Legislation.id == LegislationPriority.legislation_id,
                or_(
                    LegislationPriority.public_health_relevance >= high_priority_threshold,
                    LegislationPriority.overall_priority >= high_priority_threshold
                ),
                LegislationPriority.should_notify == True,
                LegislationPriority.notification_sent == False
            )
        ).limit(10).all()
        
        if recent_high_priority:
            # Send notification for high priority legislation
            count = self._send_legislation_notification(
                user=user,
                legislation_list=recent_high_priority,
                notification_type=NotificationTypeEnum.HIGH_PRIORITY,
                subject="High Priority Legislation Alert",
                template="high_priority_alert.html"
            )
            
            # Mark each legislation as having been notified
            for leg in recent_high_priority:
                leg.priority.notification_sent = True
                leg.priority.notification_date = datetime.utcnow()
                
            self.db_session.commit()
            
        return count
    
    def _process_new_legislation_alerts(self, user: User) -> int:
        """
        Process alerts for new legislation for a user.
        (Placeholder implementation; extend with actual functionality as needed.)
        
        Args:
            user: The user for whom to process alerts.
            
        Returns:
            Number of new legislation notifications sent.
        """
        return 0
        
    def _process_analysis_alerts(self, user: User) -> int:
        """
        Process alerts for completed analyses for a user.
        (Placeholder implementation; extend with actual functionality as needed.)
        
        Args:
            user: The user for whom to process alerts.
            
        Returns:
            Number of analysis complete notifications sent.
        """
        return 0
    
    def _send_legislation_notification(self, 
                                       user: User, 
                                       legislation_list: List[Legislation],
                                       notification_type: NotificationTypeEnum,
                                       subject: str,
                                       template: str) -> int:
        """
        Send a notification about legislation to a user.
        
        Args:
            user: The user to notify.
            legislation_list: List of legislation records to include in the notification.
            notification_type: The type of notification.
            subject: The email subject.
            template: The template name to use (for future integration with a templating engine).
            
        Returns:
            The number of notifications sent (0 or 1).
        """
        if not legislation_list:
            return 0
            
        try:
            # Check if the user has email notifications enabled
            channels = user.alert_preferences.alert_channels or {"email": True}
            if not channels.get("email", True):
                return 0
                
            # Build a simple HTML email content
            email_content = f"<h1>{subject}</h1><ul>"
            for leg in legislation_list:
                email_content += f"<li><strong>{leg.bill_number}</strong>: {leg.title}</li>"
            email_content += "</ul><p>Visit PolicyPulse for more details.</p>"
            
            # Send the email using SMTP
            self._send_email(
                recipient=user.email,
                subject=subject,
                html_content=email_content
            )
            
            # Record the notification in the alert history
            for leg in legislation_list:
                alert_history = AlertHistory(
                    user_id=user.id,
                    legislation_id=leg.id,
                    alert_type=notification_type,
                    alert_content=f"{leg.bill_number}: {leg.title}",
                    delivery_status="sent"
                )
                self.db_session.add(alert_history)
                
            self.db_session.commit()
            return 1
            
        except Exception as e:
            logger.error(f"Error sending notification to {user.email}: {e}")
            self.db_session.rollback()
            return 0
    
    def _send_email(self, recipient: str, subject: str, html_content: str) -> bool:
        """
        Send an email using SMTP.
        
        Args:
            recipient: The email recipient.
            subject: The email subject.
            html_content: The HTML content of the email.
            
        Returns:
            True if the email was sent successfully; False otherwise.
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config["from_email"]
            msg['To'] = recipient
            
            # Attach the HTML content to the email
            msg.attach(MIMEText(html_content, 'html'))
            
            # Connect to the SMTP server, initiate TLS, log in if credentials provided, and send the email
            with smtplib.SMTP(self.smtp_config["server"], self.smtp_config["port"]) as server:
                server.starttls()
                if self.smtp_config["username"] and self.smtp_config["password"]:
                    server.login(self.smtp_config["username"], self.smtp_config["password"])
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return False
