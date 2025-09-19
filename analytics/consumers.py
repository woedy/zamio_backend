import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from .services import analytics_aggregator

User = get_user_model()


class AnalyticsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time analytics updates"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Determine user type and set appropriate group
        self.user_type = await self.get_user_type()
        self.user_id = str(self.user.id)
        
        # Join appropriate groups based on user type
        if self.user_type == 'artist':
            self.artist_id = await self.get_artist_id()
            if self.artist_id:
                await self.channel_layer.group_add(
                    f"analytics_artist_{self.artist_id}",
                    self.channel_name
                )
        elif self.user_type == 'station':
            self.station_id = await self.get_station_id()
            if self.station_id:
                await self.channel_layer.group_add(
                    f"analytics_station_{self.station_id}",
                    self.channel_name
                )
        elif self.user_type == 'publisher':
            self.publisher_id = await self.get_publisher_id()
            if self.publisher_id:
                await self.channel_layer.group_add(
                    f"analytics_publisher_{self.publisher_id}",
                    self.channel_name
                )
        elif self.user_type == 'admin':
            await self.channel_layer.group_add(
                "analytics_admin",
                self.channel_name
            )
        
        # Join general analytics group
        await self.channel_layer.group_add(
            "analytics_general",
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        # Leave all groups
        if hasattr(self, 'user_type'):
            if self.user_type == 'artist' and hasattr(self, 'artist_id'):
                await self.channel_layer.group_discard(
                    f"analytics_artist_{self.artist_id}",
                    self.channel_name
                )
            elif self.user_type == 'station' and hasattr(self, 'station_id'):
                await self.channel_layer.group_discard(
                    f"analytics_station_{self.station_id}",
                    self.channel_name
                )
            elif self.user_type == 'publisher' and hasattr(self, 'publisher_id'):
                await self.channel_layer.group_discard(
                    f"analytics_publisher_{self.publisher_id}",
                    self.channel_name
                )
            elif self.user_type == 'admin':
                await self.channel_layer.group_discard(
                    "analytics_admin",
                    self.channel_name
                )
        
        await self.channel_layer.group_discard(
            "analytics_general",
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_metrics':
                await self.handle_metrics_request(data)
            elif message_type == 'subscribe_metric':
                await self.handle_metric_subscription(data)
            elif message_type == 'unsubscribe_metric':
                await self.handle_metric_unsubscription(data)
            
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    async def handle_metrics_request(self, data):
        """Handle request for specific metrics"""
        metric_names = data.get('metrics', [])
        filters = data.get('filters', {})
        
        # Get real-time metrics
        metrics = await database_sync_to_async(
            analytics_aggregator.get_realtime_metrics
        )(metric_names, **filters)
        
        await self.send(text_data=json.dumps({
            'type': 'metrics_update',
            'metrics': metrics,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def handle_metric_subscription(self, data):
        """Handle subscription to specific metrics"""
        metric_name = data.get('metric')
        if metric_name:
            # Add to subscription group
            await self.channel_layer.group_add(
                f"metric_{metric_name}",
                self.channel_name
            )
    
    async def handle_metric_unsubscription(self, data):
        """Handle unsubscription from specific metrics"""
        metric_name = data.get('metric')
        if metric_name:
            # Remove from subscription group
            await self.channel_layer.group_discard(
                f"metric_{metric_name}",
                self.channel_name
            )
    
    async def send_initial_data(self):
        """Send initial analytics data based on user type"""
        try:
            if self.user_type == 'artist' and hasattr(self, 'artist_id'):
                # Send basic artist metrics
                end_date = timezone.now()
                start_date = end_date - timedelta(days=7)  # Last 7 days
                
                analytics_data = await database_sync_to_async(
                    analytics_aggregator.get_artist_analytics
                )(self.artist_id, (start_date, end_date))
                
                await self.send(text_data=json.dumps({
                    'type': 'initial_data',
                    'user_type': 'artist',
                    'data': analytics_data
                }))
            
            elif self.user_type == 'station' and hasattr(self, 'station_id'):
                # Send basic station metrics
                end_date = timezone.now()
                start_date = end_date - timedelta(days=7)
                
                analytics_data = await database_sync_to_async(
                    analytics_aggregator.get_station_analytics
                )(self.station_id, (start_date, end_date))
                
                await self.send(text_data=json.dumps({
                    'type': 'initial_data',
                    'user_type': 'station',
                    'data': analytics_data
                }))
            
            elif self.user_type == 'publisher' and hasattr(self, 'publisher_id'):
                # Send basic publisher metrics
                end_date = timezone.now()
                start_date = end_date - timedelta(days=30)  # Last 30 days
                
                analytics_data = await database_sync_to_async(
                    analytics_aggregator.get_publisher_analytics
                )(self.publisher_id, (start_date, end_date))
                
                await self.send(text_data=json.dumps({
                    'type': 'initial_data',
                    'user_type': 'publisher',
                    'data': analytics_data
                }))
            
            elif self.user_type == 'admin':
                # Send basic admin metrics
                end_date = timezone.now()
                start_date = end_date - timedelta(days=30)
                
                analytics_data = await database_sync_to_async(
                    analytics_aggregator.get_admin_analytics
                )((start_date, end_date))
                
                await self.send(text_data=json.dumps({
                    'type': 'initial_data',
                    'user_type': 'admin',
                    'data': analytics_data
                }))
        
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to load initial data: {str(e)}'
            }))
    
    # WebSocket message handlers for group messages
    async def analytics_update(self, event):
        """Handle analytics update messages from groups"""
        await self.send(text_data=json.dumps({
            'type': 'analytics_update',
            'data': event['data'],
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    async def metric_update(self, event):
        """Handle metric update messages"""
        await self.send(text_data=json.dumps({
            'type': 'metric_update',
            'metric': event['metric'],
            'value': event['value'],
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    async def system_alert(self, event):
        """Handle system alert messages"""
        await self.send(text_data=json.dumps({
            'type': 'system_alert',
            'alert': event['alert'],
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # Helper methods
    @database_sync_to_async
    def get_user_type(self):
        """Determine user type based on related models"""
        if hasattr(self.user, 'artists') and self.user.artists.exists():
            return 'artist'
        elif hasattr(self.user, 'station_user') and self.user.station_user.exists():
            return 'station'
        elif hasattr(self.user, 'publisher_profile'):
            return 'publisher'
        elif self.user.is_staff or self.user.is_superuser:
            return 'admin'
        return 'unknown'
    
    @database_sync_to_async
    def get_artist_id(self):
        """Get artist ID for the user"""
        try:
            artist = self.user.artists.filter(active=True).first()
            return artist.artist_id if artist else None
        except:
            return None
    
    @database_sync_to_async
    def get_station_id(self):
        """Get station ID for the user"""
        try:
            station = self.user.station_user.filter(active=True).first()
            return station.station_id if station else None
        except:
            return None
    
    @database_sync_to_async
    def get_publisher_id(self):
        """Get publisher ID for the user"""
        try:
            return self.user.publisher_profile.id if hasattr(self.user, 'publisher_profile') else None
        except:
            return None


class RealtimeMetricsConsumer(AsyncWebsocketConsumer):
    """Dedicated consumer for high-frequency real-time metrics"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join real-time metrics group
        await self.channel_layer.group_add(
            "realtime_metrics",
            self.channel_name
        )
        
        await self.accept()
        
        # Start periodic updates
        self.update_task = asyncio.create_task(self.periodic_updates())
    
    async def disconnect(self, close_code):
        # Cancel periodic updates
        if hasattr(self, 'update_task'):
            self.update_task.cancel()
        
        await self.channel_layer.group_discard(
            "realtime_metrics",
            self.channel_name
        )
    
    async def periodic_updates(self):
        """Send periodic metric updates"""
        while True:
            try:
                # Get current real-time metrics
                metrics = await database_sync_to_async(
                    analytics_aggregator.get_realtime_metrics
                )([
                    'active_detections',
                    'processing_queue',
                    'system_load',
                    'error_rate'
                ])
                
                await self.send(text_data=json.dumps({
                    'type': 'realtime_metrics',
                    'metrics': metrics,
                    'timestamp': timezone.now().isoformat()
                }))
                
                # Wait 5 seconds before next update
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error and continue
                await asyncio.sleep(5)
    
    async def realtime_update(self, event):
        """Handle real-time metric updates from groups"""
        await self.send(text_data=json.dumps({
            'type': 'realtime_update',
            'metric': event['metric'],
            'value': event['value'],
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))