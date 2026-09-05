import hashlib
import logging
from typing import Optional, Dict, Any
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

class MetadataWorker:
    @staticmethod
    def _parse_track_number(raw_val: Any) -> int:
        """Safely parse track number from metadata tags (e.g., '3/12' or 3)."""
        if not raw_val:
            return 0
        try:
            val_str = str(raw_val).split('/')[0].strip()
            return int(val_str)
        except (ValueError, TypeError, IndexError) as ex:
            logger.debug("Failed parsing track number '%s': %s", raw_val, ex)
            return 0

    def _init_track_info(self, file_path: str, f: mutagen.File) -> Dict[str, Any]:
        """Initialize default track information dictionary."""
        return {
            'path': file_path,
            'title': 'Unknown',
            'artist': 'Unknown',
            'album': 'Unknown',
            'track_number': 0,
            'duration': f.info.length if hasattr(f.info, 'length') else 0.0,
            'sample_rate': f.info.sample_rate if hasattr(f.info, 'sample_rate') else 44100,
            'bit_depth': getattr(f.info, 'bits_per_sample', 16),
            'channels': getattr(f.info, 'channels', 2),
            'cover_hash': '',
            '_cover_bytes': None
        }

    def _extract_flac(self, f: FLAC, track_info: Dict[str, Any]) -> None:
        """Extract Vorbis comment tags and embedded picture from FLAC file."""
        track_info['title'] = f.get('title', ['Unknown'])[0]
        track_info['artist'] = f.get('artist', ['Unknown'])[0]
        track_info['album'] = f.get('album', ['Unknown'])[0]
        track_info['track_number'] = self._parse_track_number(f.get('tracknumber', ['0'])[0])
        if f.pictures:
            track_info['_cover_bytes'] = f.pictures[0].data

    def _extract_mp3(self, f: MP3, track_info: Dict[str, Any]) -> None:
        """Extract ID3 tags and APIC picture frame from MP3 file."""
        if 'TIT2' in f:
            track_info['title'] = str(f['TIT2'])
        if 'TPE1' in f:
            track_info['artist'] = str(f['TPE1'])
        if 'TALB' in f:
            track_info['album'] = str(f['TALB'])
        if 'TRCK' in f:
            track_info['track_number'] = self._parse_track_number(f['TRCK'])
        if not getattr(f, 'tags', None):
            return
        for key, tag in f.tags.items():
            if key.startswith('APIC:') or key == 'APIC':
                track_info['_cover_bytes'] = getattr(tag, 'data', None)
                break

    def _extract_generic(self, f: Any, track_info: Dict[str, Any]) -> None:
        """Extract generic fallback audio metadata tags."""
        if hasattr(f, 'get'):
            track_info['title'] = f.get('title', ['Unknown'])[0] if 'title' in f else 'Unknown'
            track_info['artist'] = f.get('artist', ['Unknown'])[0] if 'artist' in f else 'Unknown'
            track_info['album'] = f.get('album', ['Unknown'])[0] if 'album' in f else 'Unknown'

    def extract(self, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            f = mutagen.File(file_path)
            if f is None:
                return None

            track_info = self._init_track_info(file_path, f)
            if isinstance(f, FLAC):
                self._extract_flac(f, track_info)
            elif isinstance(f, MP3):
                self._extract_mp3(f, track_info)
            else:
                self._extract_generic(f, track_info)

            if track_info['_cover_bytes']:
                track_info['cover_hash'] = hashlib.sha256(track_info['_cover_bytes']).hexdigest()

            return track_info
        except Exception as e:
            logger.error("Error extracting metadata for %s: %s", file_path, e)
            return None
