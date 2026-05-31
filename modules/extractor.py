import os
import re
import logging
from datetime import datetime
from typing import Any, Dict, List

try:
	import fitz  # pymupdf
	_HAS_PYMUPDF = True
except Exception:
	fitz = None
	_HAS_PYMUPDF = False

try:
	from docx import Document
	_HAS_PYTHON_DOCX = True
except Exception:
	Document = None
	_HAS_PYTHON_DOCX = False

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

try:
	from sklearn.feature_extraction.text import TfidfVectorizer
	_HAS_SKLEARN = True
except Exception:
	TfidfVectorizer = None
	_HAS_SKLEARN = False


def read_file_text(file_path: str) -> Dict[str, Any]:
	"""Read supported document and return a standardized result dict.

	Returns a dict with at least the keys:
	  - success: bool
	  - format: 'pdf'|'docx'|'txt' (on success)
	  - raw_text: str (on success)
	  - filename: str
	On error returns keys: success=False, error_type, message, file_path
	"""
	if not os.path.exists(file_path):
		return {
			'success': False,
			'error_type': 'file_not_found',
			'message': f'File not found: {file_path}',
			'file_path': file_path,
		}

	ext = os.path.splitext(file_path)[1].lower()
	filename = os.path.basename(file_path)

	try:
		if ext == '.pdf':
			if not _HAS_PYMUPDF:
				return {
					'success': False,
					'error_type': 'missing_dependency',
					'message': 'pymupdf (fitz) is not installed',
					'file_path': file_path,
				}
			text = _read_pdf(file_path)
			return {
				'success': True,
				'format': 'pdf',
				'raw_text': text,
				'filename': filename,
			}

		if ext == '.docx':
			if not _HAS_PYTHON_DOCX:
				return {
					'success': False,
					'error_type': 'missing_dependency',
					'message': 'python-docx is not installed',
					'file_path': file_path,
				}
			text = _read_docx(file_path)
			return {
				'success': True,
				'format': 'docx',
				'raw_text': text,
				'filename': filename,
			}

		if ext == '.txt':
			with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
				text = f.read()
			return {
				'success': True,
				'format': 'txt',
				'raw_text': text,
				'filename': filename,
			}

		return {
			'success': False,
			'error_type': 'unsupported_format',
			'message': f'Unsupported file extension: {ext}',
			'file_path': file_path,
		}

	except Exception as exc:  # defensive: never crash caller
		logger.exception('Error reading file %s', file_path)
		return {
			'success': False,
			'error_type': 'read_error',
			'message': str(exc),
			'file_path': file_path,
		}


def _read_pdf(file_path: str) -> str:
	"""Return concatenated text of all pages in a PDF using pymupdf.

	Raises when pymupdf missing or file cannot be read.
	"""
	doc = fitz.open(file_path)
	parts = []
	for page in doc:
		parts.append(page.get_text())
	return "\n".join(parts)


def _read_docx(file_path: str) -> str:
	"""Return concatenated paragraph text from a .docx file."""
	doc = Document(file_path)
	return "\n".join([p.text for p in doc.paragraphs])


def extract_cv_fields(file_path: str) -> Dict[str, Any]:
	"""Extract basic CV information from a supported document file."""
	base = read_file_text(file_path)
	if not base.get('success'):
		return base

	text = base['raw_text']
	return {
		'success': True,
		'format': base['format'],
		'filename': base['filename'],
		'personal_info': {
			'name': extract_name(text),
			'email': extract_email(text),
			'phone': extract_phone(text),
		},
		'skills': extract_skills(text),
		'keywords': extract_keywords(text, top_n=30),
		'raw_text': text,
	}


def extract_email(text: str) -> str:
	"""Extract the first email found in the text."""
	pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
	matches = re.findall(pattern, text)
	return matches[0] if matches else ''


def extract_phone(text: str) -> str:
	"""Extract a phone-like sequence from the text."""
	pattern = r'(?:\+\d{1,3}[\s-]*)?(?:\d{2,4}[\s-]*){2,4}\d{2,4}'
	matches = re.findall(pattern, text)
	return re.sub(r'\s+', ' ', matches[0].strip()) if matches else ''


def extract_name(text: str) -> str:
	"""Extract a likely name from the CV text using simple heuristics."""
	lines = [line.strip() for line in text.splitlines() if line.strip()]
	if not lines:
		return ''

	email = extract_email(text)
	phone = extract_phone(text)
	for idx, line in enumerate(lines[:8]):
		if email and email in line and idx > 0:
			return lines[idx - 1]
		if phone and phone in line and idx > 0:
			return lines[idx - 1]

	for line in lines[:3]:
		if 2 <= len(line.split()) <= 5 and any(word[0].isupper() for word in line.split() if word):
			return line

	return lines[0]


def extract_skills(text: str, skills_list: List[str] = None) -> List[str]:
	"""Extract relevant skill-like terms from the text using TF-IDF.

	This function replaces the fixed SKILLS dictionary with an automatic
	keyword extraction approach. It keeps the old signature for compatibility.
	"""
	if not _HAS_SKLEARN or not text:
		return []
	return extract_keywords(text, top_n=20)


def extract_keywords(text: str, top_n: int = 20) -> List[str]:
	"""Extract top-n keyword candidates from text using TF-IDF (unigrams and bigrams).

	If scikit-learn is not available returns an empty list.
	"""
	if not _HAS_SKLEARN or not text or top_n <= 0:
		return []

	vectorizer = TfidfVectorizer(
		ngram_range=(1, 2),
		stop_words='spanish',
		max_df=0.85,
		max_features=top_n * 5,
		token_pattern=r'(?u)\b\w\w+\b',
	)
	matrix = vectorizer.fit_transform([text])
	scores = matrix.toarray()[0]
	features = vectorizer.get_feature_names_out()
	idx_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
	keywords = []
	for idx, score in idx_scores:
		if score <= 0:
			break
		keywords.append(features[idx])
		if len(keywords) >= top_n:
			break
	return keywords


__all__ = [
	"read_file_text",
	"extract_cv_fields",
	"extract_email",
	"extract_phone",
	"extract_name",
	"extract_skills",
	"extract_keywords",
]

