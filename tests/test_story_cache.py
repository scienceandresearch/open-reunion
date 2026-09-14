"""Animation preparation preserves pixels and keeps decoding outside live pacing."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from test_story_cinema import rules,frame
from openreunion.dos.content import ContentSource
from openreunion.dos.assets import Picture


class StoryCacheTests(unittest.TestCase):
    def source(self,directory):
        source=ContentSource.__new__(ContentSource);source.root=Path(directory);source.bundled=False
        source.catalog={'story_cinema':rules()};source.story_animation_cache={}
        source.indexed_picture=Mock(return_value=Picture(3,1,b'\0'*3,bytes(range(256))*3))
        folder=source.root/'ANIM';folder.mkdir()
        for asset in (8,9,13):
            (folder/f'MAIN{asset}.ANI').write_bytes(frame(b'\1\2\3')+frame(b'\x81\x09\x81')+frame(b'\x82\x08'))
        return source

    def test_prepared_original_frames_and_palette_need_no_further_io(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);catalog=deepcopy(source.catalog)
            source.prepare_story_scene(9);self.assertEqual(source.indexed_picture.call_count,2)
            with patch.object(Path,'open',side_effect=AssertionError('unexpected live I/O')):
                for _ in range(3):
                    self.assertEqual(source.story_animation(8,3).pixels,b'\1\x09\x08')
                    self.assertEqual(source.story_animation(9,2).pixels,b'\1\x09\3')
                    self.assertEqual(source.story_animation(8,1).palette,bytes(range(256))*3)
            self.assertEqual(source.indexed_picture.call_count,2);self.assertEqual(source.catalog,catalog)

    def test_cache_remains_bounded_when_another_scene_is_prepared(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);source.prepare_story_scene(9);source.prepare_story_scene(10)
            self.assertEqual(len(source.story_animation_cache),2);self.assertIn(13,source.story_animation_cache)
            self.assertEqual(source.story_animation(8,3).pixels,b'\1\x09\x08')
            self.assertEqual(len(source.story_animation_cache),2)

    def test_converted_content_and_static_scenes_do_not_preload_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(directory);source.prepare_story_scene(3)
            self.assertFalse(source.story_animation_cache);self.assertFalse(source.indexed_picture.called)
            source.bundled=True;source.prepare_story_scene(9)
            self.assertFalse(source.story_animation_cache)


if __name__=='__main__':unittest.main()
