import hashlib
import logging
from typing import Optional, Dict, Any
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

class MetadataWorker:
    def extract(self, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            f = mutagen.File(file_path)
            if f is None:
                return None

            track_info = {
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

            if isinstance(f, FLAC):
                track_info['title'] = f.get('title', ['Unknown'])[0]
                track_info['artist'] = f.get('artist', ['Unknown'])[0]
                track_info['album'] = f.get('album', ['Unknown'])[0]
                try:
                    track_info['track_number'] = int(f.get('tracknumber', ['0'])[0].split('/')[0])
                except ValueError:
                    pass
                if f.pictures:
                    track_info['_cover_bytes'] = f.pictures[0].data

            elif isinstance(f, MP3):
                if 'TIT2' in f:
                    track_info['title'] = str(f['TIT2'])
                if 'TPE1' in f:
                    track_info['artist'] = str(f['TPE1'])
                if 'TALB' in f:
                    track_info['album'] = str(f['TALB'])
                if 'TRCK' in f:
                    try:
                        track_info['track_number'] = int(str(f['TRCK']).split('/')[0])
                    except ValueError:
                        pass
                        
                for key in f.tags.keys():
                    if key.startswith('APIC:'):
                        track_info['_cover_bytes'] = f.tags[key].data
                        break
            
            else:
                track_info['title'] = f.get('title', ['Unknown'])[0] if 'title' in f else 'Unknown'
                track_info['artist'] = f.get('artist', ['Unknown'])[0] if 'artist' in f else 'Unknown'
                track_info['album'] = f.get('album', ['Unknown'])[0] if 'album' in f else 'Unknown'

            if track_info['_cover_bytes']:
                h = hashlib.sha256(track_info['_cover_bytes']).hexdigest()
                track_info['cover_hash'] = h

            return track_info
        except Exception as e:
            logger.error(f"Error extracting metadata for {file_path}: {e}")
            return None
