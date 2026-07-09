"""
medium.py – Medium article download logic powered by BeautifulSoup & html2text.
"""

from __future__ import annotations

import os
import requests
from bs4 import BeautifulSoup
import html2text
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import Callable

from .utils import build_output_path, sanitize_filename
from .youtube import DownloadResult, VideoInfo


def _get_best_srcset_url(srcset: str) -> str | None:
    """Parse srcset and return the URL with the largest width resolution."""
    if not srcset:
        return None
    candidates = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        url = tokens[0]
        width = 0
        if len(tokens) > 1:
            w_str = tokens[1].lower()
            if w_str.endswith("w"):
                try:
                    width = int(w_str[:-1])
                except ValueError:
                    pass
        candidates.append((width, url))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


class MediumDownloader:
    """Downloader class for fetching and converting Medium articles to Markdown."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_freedium_url(self, url: str) -> str:
        """Helper to convert any Medium URL to a Freedium URL to bypass paywalls."""
        url = url.strip()
        if "freedium.cfd" in url:
            return url
        
        # Ensure it has a scheme
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        return f"https://freedium.cfd/{url}"

    def get_info(self, url: str) -> VideoInfo:
        """
        Fetch Medium article metadata.

        Parameters
        ----------
        url:
            Medium article URL.

        Returns
        -------
        VideoInfo
        """
        freedium_url = self._get_freedium_url(url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        # Try Freedium first, fallback to original Medium URL on failure
        response_text = ""
        actual_url = freedium_url
        try:
            response = requests.get(freedium_url, headers=headers, timeout=15)
            response.raise_for_status()
            response_text = response.text
        except requests.RequestException as exc:
            if "freedium.cfd" in url:
                raise ValueError(f"Unable to access the article on Freedium: {exc}")
            
            try:
                actual_url = url
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                response_text = response.text
            except requests.RequestException as direct_exc:
                raise ValueError(
                    f"Unable to access the article. Tried Freedium and direct access.\n"
                    f"Freedium error: {exc}\n"
                    f"Direct error: {direct_exc}"
                )

        soup = BeautifulSoup(response_text, "html.parser")
        main_content = soup.find(class_="main-content") or soup.find("article")
        if not main_content:
            raise ValueError(
                "Could not parse the article content. The service may be temporary unavailable "
                "or the URL is not a supported article format."
            )

        # 1. Extract Title
        title_el = main_content.find("h1") or soup.find("h1")
        title = title_el.get_text().strip() if title_el else "Untitled Medium Article"

        # 2. Extract Author
        author = "Unknown Author"
        # Check meta tags first
        author_meta = soup.find("meta", property="author") or soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta.get("content", "").strip()
        else:
            # Look for typical Freedium elements or links
            author_link = soup.find("a", href=lambda h: h and "/@" in h)
            if author_link:
                author = author_link.get_text().strip()

        # 3. Extract Description / Subtitle
        description = ""
        desc_meta = (
            soup.find("meta", property="og:description")
            or soup.find("meta", attrs={"name": "description"})
            or soup.find("meta", property="twitter:description")
        )
        if desc_meta and desc_meta.get("content"):
            description = desc_meta.get("content", "").strip()

        # 4. Extract Thumbnail (Header image)
        thumbnail_url = ""
        og_image = soup.find("meta", property="og:image") or soup.find("meta", property="twitter:image")
        if og_image and og_image.get("content"):
            thumbnail_url = og_image.get("content", "").strip()
        else:
            # Fallback to the first image inside main article content
            # Try to find a picture tag first
            first_pic = main_content.find("picture")
            if first_pic:
                source_tags = first_pic.find_all("source")
                for src_tag in source_tags:
                    srcset = src_tag.get("srcset")
                    if srcset:
                        url_candidate = _get_best_srcset_url(srcset)
                        if url_candidate:
                            thumbnail_url = urljoin(actual_url, url_candidate)
                            break
            
            if not thumbnail_url:
                first_img = main_content.find("img")
                if first_img:
                    img_src = first_img.get("src") or first_img.get("data-src")
                    if img_src:
                        thumbnail_url = urljoin(actual_url, img_src)

        return VideoInfo(
            title=title,
            uploader=author,
            duration_seconds=0,  # Reading time estimation could go here
            view_count=0,
            thumbnail_url=thumbnail_url,
            description=description,
            webpage_url=url,
        )

    def _download_image(
        self,
        img_url: str,
        idx: int,
        title: str,
        images_dir: Path,
        actual_url: str,
        headers: dict,
    ) -> tuple[Path | None, str]:
        """Download an individual image and return local Path and relative URL."""
        abs_src = urljoin(actual_url, img_url)
        safe_prefix = sanitize_filename(title)[:50].replace(" ", "_")
        parsed_src = urlparse(abs_src)
        ext = os.path.splitext(parsed_src.path)[1]
        
        # If there is a format parameter in query string/URL, use it (e.g. format:webp -> .webp)
        if not ext or len(ext) > 5 or "/" in ext:
            if "format:webp" in abs_src or "format=webp" in abs_src:
                ext = ".webp"
            elif "format:png" in abs_src or "format=png" in abs_src:
                ext = ".png"
            elif "format:jpg" in abs_src or "format=jpg" in abs_src or "format:jpeg" in abs_src:
                ext = ".jpg"
            else:
                ext = ".png"

        img_filename = f"{safe_prefix}_img_{idx}{ext}"
        img_path = images_dir / img_filename
        rel_path = f"medium_images/{img_filename}"

        try:
            img_res = requests.get(abs_src, headers=headers, timeout=10)
            img_res.raise_for_status()
            with open(img_path, "wb") as f_img:
                f_img.write(img_res.content)
            return img_path, rel_path
        except Exception:
            return None, ""

    def download(
        self,
        url: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> DownloadResult:
        """
        Download Medium article, save images locally inside a post-specific folder, and output as Markdown.

        Parameters
        ----------
        url:
            Medium article URL.
        progress_callback:
            Optional callable receiving progress-hook dicts.

        Returns
        -------
        DownloadResult
        """
        if progress_callback:
            progress_callback({"status": "downloading", "downloaded_bytes": 100, "total_bytes": 1000})

        freedium_url = self._get_freedium_url(url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # Try Freedium first, fallback to original Medium URL on failure
        response_text = ""
        actual_url = freedium_url
        try:
            response = requests.get(freedium_url, headers=headers, timeout=15)
            response.raise_for_status()
            response_text = response.text
        except requests.RequestException as exc:
            if "freedium.cfd" in url:
                return DownloadResult(success=False, error_message=f"Failed to download article HTML from Freedium: {exc}")
            
            try:
                actual_url = url
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                response_text = response.text
            except requests.RequestException as direct_exc:
                return DownloadResult(
                    success=False,
                    error_message=(
                        f"Failed to download article HTML. Tried Freedium and direct access.\n"
                        f"Freedium error: {exc}\n"
                        f"Direct error: {direct_exc}"
                    )
                )

        if progress_callback:
            progress_callback({"status": "downloading", "downloaded_bytes": 400, "total_bytes": 1000})

        soup = BeautifulSoup(response_text, "html.parser")
        main_content = soup.find(class_="main-content") or soup.find("article")
        if not main_content:
            return DownloadResult(success=False, error_message="Could not find the article body.")

        # Extract title for filename and directory naming
        title_el = main_content.find("h1") or soup.find("h1")
        title = title_el.get_text().strip() if title_el else "Untitled Medium Article"

        # Create a dedicated directory for the article
        post_dir = build_output_path(self.output_dir, title, "")
        post_dir.mkdir(parents=True, exist_ok=True)

        # Images are saved in a subfolder relative to the markdown file
        images_dir = post_dir / "medium_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Download images locally and update HTML references
        # 1. Process `<picture>` tags first
        picture_tags = main_content.find_all("picture")
        total_pics = len(picture_tags)
        img_counter = 1

        for idx, pic_tag in enumerate(picture_tags, 1):
            source_tags = pic_tag.find_all("source")
            best_url = None
            for src_tag in source_tags:
                srcset = src_tag.get("srcset")
                if srcset:
                    url_candidate = _get_best_srcset_url(srcset)
                    if url_candidate:
                        best_url = url_candidate
                        break
            
            if not best_url:
                inner_img = pic_tag.find("img")
                if inner_img:
                    best_url = inner_img.get("src") or inner_img.get("data-src") or inner_img.get("data-zoom-src")

            if best_url:
                img_path, rel_path = self._download_image(best_url, img_counter, title, images_dir, actual_url, headers)
                if img_path:
                    new_img = soup.new_tag("img", src=rel_path)
                    inner_img = pic_tag.find("img")
                    if inner_img and inner_img.get("alt"):
                        new_img["alt"] = inner_img["alt"]
                    pic_tag.replace_with(new_img)
                    img_counter += 1

            if progress_callback and total_pics > 0:
                pct = int(400 + (idx / total_pics) * 250)
                progress_callback({"status": "downloading", "downloaded_bytes": pct, "total_bytes": 1000})

        # 2. Process remaining standalone `<img>` tags
        img_tags = main_content.find_all("img")
        total_imgs = len(img_tags)
        
        for idx, img_tag in enumerate(img_tags, 1):
            if img_tag.find_parent("picture"):
                continue  # Already processed

            src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-zoom-src")
            if not src:
                continue
            if src.startswith("data:image"):
                continue

            img_path, rel_path = self._download_image(src, img_counter, title, images_dir, actual_url, headers)
            if img_path:
                img_tag["src"] = rel_path
                img_counter += 1

            if progress_callback and total_imgs > 0:
                pct = int(650 + (idx / total_imgs) * 250)
                progress_callback({"status": "downloading", "downloaded_bytes": pct, "total_bytes": 1000})

        # Convert the modified HTML to Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0  # Do not wrap lines
        
        # Clean up some common clutter tags if present in the BeautifulSoup representation
        for tag in main_content.find_all(["button", "script", "style", "iframe"]):
            tag.decompose()

        markdown_content = h.handle(str(main_content))

        # Build output path for the Markdown file (saved directly inside post_dir)
        output_file = post_dir / f"{sanitize_filename(title)}.md"

        try:
            with open(output_file, "w", encoding="utf-8") as f_md:
                f_md.write(markdown_content)
        except IOError as exc:
            return DownloadResult(success=False, error_message=f"Failed to save Markdown file: {exc}")

        if progress_callback:
            progress_callback({"status": "finished"})

        return DownloadResult(
            success=True,
            file_path=output_file,
            file_size_bytes=output_file.stat().st_size,
        )
