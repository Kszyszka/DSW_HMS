from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
    
    def ready(self):
        """Import sygnałów gdy aplikacja jest gotowa"""
        import core.signals  # noqa