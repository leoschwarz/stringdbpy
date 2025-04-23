import json
import shutil
import requests
from pathlib import Path
from loguru import logger

from gsea_session import GSEASession

class StringGSEAResults:
    """
    Handles serializing, writing, and zipping of STRING-db GSEA results using a GSEASession.
    """

    def __init__(self, session: GSEASession):
        self.session = session

        # Results payloads should already be in session.res_data
        if not self.session.res_data:
            raise RuntimeError("Session contains no result data. Ensure you've polled before building results.")

    def get_res_path(self) -> Path:
        """
        Get or create the directory for all outputs.
        """
        path = self.session.base_path / f"WU_{self.session.workunit_id}_GSEA"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_links(self) -> dict:
        """
        Extract page URLs for all successful runs.
        """
        links = {}
        for (outer, inner), data in self.session.res_data.items():
            if data.get('status') == 'success' and 'page_url' in data:
                links.setdefault(outer, {})[inner] = data['page_url']
        return links

    def write_links(self) -> dict:
        """
        Write links.txt for each outer key and return paths.
        """
        written = {}
        base = self.get_res_path()
        for outer, inners in self.get_links().items():
            sub = base / outer
            sub.mkdir(parents=True, exist_ok=True)
            file_path = sub / 'links.txt'
            with open(file_path, 'w') as f:
                for inner, url in inners.items():
                    f.write(f"{inner}: {url}\n")
            logger.info(f"Wrote links file: {file_path}")
            written[outer] = file_path
        return written

    def _write_gsea_files(self, file_type: str, url_key: str, suffix: str) -> Path:
        """
        Download and save TSV or PNG files for all successful runs.
        """
        base = self.get_res_path()
        for (outer, inner), data in self.session.res_data.items():
            if data.get('status') != 'success' or url_key not in data:
                continue
            url = data[url_key]
            resp = requests.get(url)
            resp.raise_for_status()

            sub = base / outer
            sub.mkdir(parents=True, exist_ok=True)
            file_path = sub / f"{inner}{suffix}"
            with open(file_path, 'wb') as f:
                f.write(resp.content)
            logger.info(f"Saved {file_type}: {file_path}")
        return base

    def write_gsea_tsv(self) -> Path:
        """Download and save all result TSVs."""
        return self._write_gsea_files('results', 'download_url', '_results.tsv')

    def write_gsea_graphs(self) -> Path:
        """Download and save all result graphs as PNGs."""
        return self._write_gsea_files('graph', 'graph_url', '_results.png')

    def serialize_results(self) -> Path:
        """
        Dump the full session (config + results) to JSON in the results folder.
        """
        serial = {}
        for (outer, inner), val in self.session.res_data.items():
            serial[f"{outer}~{inner}"] = val

        payload = {
            'config': {
                'config_dict': self.session.config_dict,
                'workunit_id': self.session.workunit_id,
                'species': self.session.species,
                'base_path': str(self.session.base_path)
            },
            'results': serial
        }

        outdir = self.get_res_path()
        file_path = outdir / 'serialized_gsea_session.json'
        with open(file_path, 'w') as f:
            json.dump(payload, f, indent=2)
        logger.info(f"Serialized results to {file_path}")
        return file_path

    @staticmethod
    def zip_folder(folder_path: Path) -> Path:
        """Create a .zip archive of the given folder."""
        archive = shutil.make_archive(str(folder_path.parent / folder_path.name), 'zip', root_dir=str(folder_path))
        return Path(archive)
