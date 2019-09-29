# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Telegram lottie sticker converter
# Copyright (C) 2019 Randall Eramde Lawrence
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import logging
from io import BytesIO
from typing import Optional, Tuple


LOG: logging.Logger = logging.getLogger("mau.util.tgs")

try:
    import gzip
    import subprocess

    proc = subprocess.Popen(["lottieconverter"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, err = proc.communicate()
    if err is not None and not err.decode("utf-8").startswith("Usage"):
        raise ImportError(err)


    def _tgs_to_png(file: bytes, width: int,
                    height: int, frame: int = None) -> Tuple[bytes, Optional[bytes]]:
        if not frame:
            frame = 1
        p = subprocess.run(["lottieconverter", "-", "-", "png",
                           str.format(f"{width}x{height}"), str(frame)], stdout=subprocess.PIPE,
                           input=file, universal_newlines=False)
        return p.stdout, None


    TGS_CONVERTERS = {"png": _tgs_to_png}

    def _tgs_to_gif(file: bytes, width: int, height: int) -> Tuple[bytes, Optional[bytes]]:
        p = subprocess.run(["lottieconverter", "-", "-", "gif",
                            str.format(f"{width}x{height}"), "0", "0x202020"],
                           stdout=subprocess.PIPE,
                           input=file, universal_newlines=False)
        return p.stdout, None

    TGS_CONVERTERS.update({"gifc": _tgs_to_gif})

    try:
        from PIL import Image

        def _tgs_to_gif(file: bytes, width: int, height: int) \
                -> Tuple[bytes, Optional[bytes]]:
            frames = []
            first_frame = None
            for i in range(1, 100):
                frame, _ = _tgs_to_png(file, width, height, i)
                if not first_frame:
                    first_frame = frame
                image = Image.open(BytesIO(frame))
                if image.mode not in ["RGBA", "RGBa"]:
                    image = image.convert("RGBA")
                alpha = image.getchannel("A")
                image = image.convert('P', palette=Image.ADAPTIVE, colors=255)
                mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
                image.paste(255, mask)
                frames.append(image)

            duration = 100
            fo = BytesIO()
            frames[0].save(
                fo,
                format='GIF',
                append_images=frames[1:],
                save_all=True,
                duration=duration,
                loop=0,
                transparency=255,
                disposal=2,
            )
            return fo.getvalue(), first_frame

        TGS_CONVERTERS.update({"gif": _tgs_to_gif})
    except ImportError:
        LOG.warn("Unable to create tgs to gif converter, install PIL")

    try:
        import cv2
        import numpy
        import tempfile
        import os

        def _tgs_to_video(file: bytes, width: int, height: int) \
                -> Tuple[bytes, Optional[bytes]]:
            with tempfile.NamedTemporaryFile(mode="r+b", suffix=".mp4") as tmp:
                video_tmp_file = tmp.name
            video = None
            first_frame = None
            try:
                video = cv2.VideoWriter(filename=video_tmp_file, apiPreference=cv2.CAP_ANY,
                                        fourcc=cv2.VideoWriter_fourcc(*'vp09'),
                                        fps=10,
                                        frameSize=(width, height))

                for i in range(1, 100):
                    frame, _ = _tgs_to_png(file, width, height, i)
                    if not first_frame:
                        first_frame = frame
                    video.write(cv2.cvtColor(numpy.array(Image.open(BytesIO(frame))),
                                             cv2.COLOR_RGB2BGR))

            finally:
                if video:
                    video.release()
            with open(video_tmp_file, "rb") as video_file:
                out = video_file.read()
            os.remove(video_tmp_file)
            return out, first_frame
        """
        It seems, that riot don't wont to play converted videos...
        """
        TGS_CONVERTERS.update({"mp4": _tgs_to_video})
    except ImportError:
        LOG.warn("Unable to create tgs to video converter, "
                 "install PIL, numpy and opencv-python-headless")

except (ImportError, OSError):
    LOG.exception("Unable to init tgs converters, possibly missing lottieconverter")
    TGS_CONVERTERS = {}


TYPE_TO_MIME = {"png": "image/png", "gif": "image/gif", "gifc": "image/gif", "mp4": "video/mp4"}


def convert_tgs_to(file: bytes, convert_to: str, width: int = 200, height: int = 200) \
        -> Tuple[str, bytes, Optional[int], Optional[int], Optional[bytes]]:
    if convert_to in TGS_CONVERTERS:
        mime = TYPE_TO_MIME[convert_to]
        converter = TGS_CONVERTERS[convert_to]
        out, preview = converter(file, width, height)
        return mime, out, width, height, preview
    else:
        LOG.warning(f"Unable to convert animated sticker, type {convert_to} not supported")
    return "application/gzip", file, None, None, None
