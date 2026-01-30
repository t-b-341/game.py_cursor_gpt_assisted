# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for the game
# Run with: pyinstaller MyGame.spec

import os

a = Analysis(
    ['game.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Asset folders
        ('assets', 'assets'),
        ('config', 'config'),
        ('Game Sound FX', 'Game Sound FX'),
        # Root data files
        ('controls.json', '.'),
        ('saves.json', '.'),
        ('profiles.json', '.'),
    ],
    hiddenimports=[
        # Core game modules that may be dynamically imported
        'systems',
        'systems.audio_system',
        'systems.collision_system',
        'systems.movement_system',
        'systems.spawn_system',
        'systems.ai_system',
        'systems.camera',
        'systems.fps_tracker',
        'scenes',
        'scenes.title',
        'scenes.options',
        'scenes.gameplay',
        'scenes.pause',
        'scenes.shader_settings',
        'scenes.shader_test',
        'shader_effects',
        'shader_effects.pipeline',
        'shader_effects.registry',
        'rendering',
        'rendering.world',
        'rendering.hud',
        'engine',
        'engine.render_loop',
        'engine.input_loop',
        'telemetry',
        'telemetry.writer',
        # Third-party that may be missed
        'pygame',
        'pygame.mixer',
        'pygame.font',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules from build
        'pytest',
        'tests',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MyGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Changed to False for windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='path/to/icon.ico'
)
