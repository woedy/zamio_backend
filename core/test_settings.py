"""
Test-specific Django settings for ZamIO backend.
Optimized for fast test execution and isolation.
"""

from .settings import *
import tempfile

# Use in-memory SQLite for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        }
    }
}

# Disable migrations for faster test setup
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Use dummy cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Use console email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable Celery for tests (use synchronous execution)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory channel layer for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
    },
}

# Use temporary directory for media files during tests
MEDIA_ROOT = tempfile.mkdtemp()

# Disable password validation for tests
AUTH_PASSWORD_VALIDATORS = []

# Use weaker password hashing for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Test-specific configurations
TEST_AUDIO_FILE_PATH = BASE_DIR / 'test_data' / 'audio'
TEST_FINGERPRINT_DATA = {
    'sample_rate': 22050,
    'duration': 30.0,
    'confidence_threshold': 0.8
}

# Mock external services for tests
ACRCLOUD_ACCESS_KEY = 'test_key'
ACRCLOUD_ACCESS_SECRET = 'test_secret'
ACRCLOUD_HOST = 'test.acrcloud.com'

# Disable rate limiting for tests
RATE_LIMIT_ENABLED = False

# Use simple JWT settings for tests
SIMPLE_JWT.update({
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=10),
})