from flask import request, jsonify
from PIL import Image
from PIL import ExifTags
import numpy as np, piexif
import io, json
import base64
from model import doDetection
import sqlite3
import os
from datetime import datetime as dttm
from datetime import datetime as dttm

def inference():
    try:        
        lat_rational, alt_rational = ("", "")
        im = request.files.get("picture")
        cg_id = request.form.get("counting_group_id")

        if not im or not cg_id :
            return jsonify({
                "error" : "bad request, no image or counting group id selected"
            }), 400

        im_arr = np.array(Image.open(im))

        img_file = Image.open(im)
        exif_bytes = img_file.info.get('exif')
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
            gps = exif_dict["GPS"]
            lat_rational = gps.get(piexif.GPSIFD.GPSLatitude)
            lat_rational_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef).decode('ascii')
            lat_deg = lat_rational[0][0] / lat_rational[0][1]
            lat_min = lat_rational[1][0] / lat_rational[1][1]
            lat_sec = lat_rational[2][0] / lat_rational[2][1]
            latitude = lat_deg + (lat_min/60) + (lat_sec/3600)

            long_rational = gps.get(piexif.GPSIFD.GPSLongitude)
            long_rational_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef).decode('ascii')
            long_deg = long_rational[0][0] / long_rational[0][1]
            long_min = long_rational[1][0] / long_rational[1][1]
            long_sec = long_rational[2][0] / long_rational[2][1]
            longtitude = long_deg + (long_min/60) + (long_sec/3600)
            
            alt_rational = gps.get(piexif.GPSIFD.GPSAltitude)
            alt_rational = alt_rational

            datetime = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal).decode('ascii')


        labeled_im_array, count, average_confidence = doDetection(im_arr)
        labeled_im = Image.fromarray(labeled_im_array)
        
        img_io = io.BytesIO() 
        labeled_im.save(img_io, 'JPEG')
        img_io.seek(0)

        # adding file
        img_filename = f"count_{dttm.now()}.jpeg"
        with open(os.path.join(os.path.dirname(__file__), "../static/result", img_filename), "wb") as file:
            file.write(img_io.getvalue())

        # insert into db
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../database', 'logs.db'))
        cursor = conn.cursor()
        cursor.execute('''
                INSERT INTO counting (group_id, date, conf_average, count, lat, lat_ref, long, long_ref, alt, image_name) 
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cg_id ,str('%.2f' % average_confidence), f"{count}", f"{latitude}", f"{lat_rational_ref}", f"{longtitude}", f"{long_rational_ref}", f"{alt_rational}", f"{img_filename}"))
        conn.commit()
        conn.close()

        return jsonify({
            'count' : count,
            'average_confidence' : f"{average_confidence:.2f}", 
            'image' : f"/static/result/{img_filename}",
            'metadata' : {
                'gps' : {
                    'lat' : latitude or None,
                    'lat_ref' : lat_rational_ref or None,
                    'long' : longtitude or None,
                    'long_ref' : long_rational_ref or None,
                    'alt' : alt_rational or None
                },
                'datetime' : datetime
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500