from kivymd.tools.hotreload.app import MDApp
from kivy.lang import Builder


class HotReload(MDApp):
    KV_FILES = [r'app/operations.kv']
    DEBUG = True

    def build_app(self, first=False):
        return Builder.load_file(r'app/operations.kv')

HotReload().run()