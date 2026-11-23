import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PIL import Image,ImageOps,ImageFilter,ImageStat
from pypdf import PdfReader

Image.MAX_IMAGE_PIXELS=25000000
ROOT=Path(__file__).resolve().parent.parent
if (ROOT/'.tools/tesseract/tesseract.exe').exists():os.environ['PATH']=str(ROOT/'.tools/tesseract')+os.pathsep+os.environ.get('PATH','')

def ocr_image(path):
    if not shutil.which('tesseract'):raise ValueError('OCR is unavailable: install Tesseract or use the Docker image.')
    with Image.open(path) as source:
        if source.width*source.height>25000000:raise ValueError('Image exceeds 25 megapixels.')
        picture=ImageOps.exif_transpose(source).convert('RGB')
        if max(picture.size)>2600:picture.thumbnail((2600,2600))
        gray=ImageOps.grayscale(picture)
        quality={'brightness':round(ImageStat.Stat(gray).mean[0],1),'edge_variance':round(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0],1)}
        picture=ImageOps.autocontrast(gray)
        with tempfile.TemporaryDirectory() as temp:
            clean=Path(temp)/'ocr.png';picture.save(clean)
            # OSD is a best effort; short documents may not have enough text to orient.
            orientation=subprocess.run(['tesseract',str(clean),'stdout','--psm','0'],capture_output=True,timeout=20)
            import re
            rotation=re.search(r'Rotate:\s*(90|180|270)',orientation.stdout.decode(errors='replace'))
            if rotation:picture=picture.rotate(-int(rotation[1]),expand=True);picture.save(clean)
            languages='eng+hin' if (Path(os.environ.get('TESSDATA_PREFIX',ROOT/'.tools/tesseract/tessdata'))/'hin.traineddata').exists() or sys.platform!='win32' else 'eng'
            result=subprocess.run(['tesseract',str(clean),'stdout','-l',languages,'--psm','6','tsv'],capture_output=True,timeout=40)
            if result.returncode:raise ValueError('OCR failed. Verify installed language data and try a clearer document.')
            rows=list(csv.DictReader(io.StringIO(result.stdout.decode('utf-8',errors='replace')),delimiter='\t'))
            lines={};scores=[]
            for row in rows:
                if not row.get('text','').strip():continue
                key=(row['page_num'],row['block_num'],row['par_num'],row['line_num']);lines.setdefault(key,[]).append(row['text'])
                try:
                    if float(row['conf'])>=0:scores.append(float(row['conf']))
                except ValueError:pass
            return '\n'.join(' '.join(words) for words in lines.values()),round(sum(scores)/len(scores)/100,3) if scores else 0,quality

def read_document(path):
    path=Path(path);magic=path.read_bytes()[:12];metadata={'method':'text','ocr_confidence':None,'pages':0,'quality':[],'warnings':[]}
    if magic.startswith(b'%PDF-'):
        reader=PdfReader(path)
        if reader.is_encrypted:raise ValueError('Password-protected PDF. Upload an unlocked copy.')
        if not 1<=len(reader.pages)<=15:raise ValueError('PDF must contain 1 to 15 pages.')
        parts=[];confidences=[]
        for index,page in enumerate(reader.pages):
            text=page.extract_text() or ''
            if not text.strip() or bool(page.images):
                if not shutil.which('pdftoppm'):raise ValueError('OCR requires Poppler (pdftoppm).')
                with tempfile.TemporaryDirectory() as temp:
                    prefix=str(Path(temp)/'page')
                    subprocess.run(['pdftoppm','-f',str(index+1),'-l',str(index+1),'-singlefile','-scale-to','2200','-png',str(path),prefix],check=True,capture_output=True,timeout=30)
                    text,confidence,quality=ocr_image(prefix+'.png');confidences.append(confidence);metadata['quality'].append(quality)
                metadata['method']='ocr' if not parts else 'mixed'
            parts.append(text)
        metadata['pages']=len(parts);text='\n'.join(parts)
        if confidences:metadata['ocr_confidence']=round(min(confidences),3)
    elif magic.startswith(b'\x89PNG\r\n\x1a\n') or magic.startswith(b'\xff\xd8\xff'):
        text,confidence,quality=ocr_image(path);metadata.update(method='ocr',pages=1,ocr_confidence=confidence,quality=[quality])
    else:raise ValueError('Unsupported file type. Upload a PDF, PNG or JPEG.')
    if not text.strip():raise ValueError('Blank or unreadable document; upload a clearer complete invoice.')
    if len(text)>250000:raise ValueError('Extracted content exceeds the supported limit.')
    if metadata['ocr_confidence'] is not None:
        metadata['warnings'].append('OCR output must be checked against the complete source, including cropped or handwritten regions.')
        if metadata['ocr_confidence']<.85:metadata['warnings'].append('Low OCR confidence: mandatory human review.')
    return text,metadata

if __name__=='__main__':
    if sys.platform!='win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
    try:
        text,metadata=read_document(sys.argv[1]);result={'text':text,'metadata':metadata}
    except Exception as exc:result={'error':str(exc) if isinstance(exc,ValueError) else 'Invalid or malformed document.'}
    Path(sys.argv[2]).write_text(json.dumps(result),encoding='utf-8')
