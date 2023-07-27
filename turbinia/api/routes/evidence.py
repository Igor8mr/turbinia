# -*- coding: utf-8 -*-
# Copyright 2022 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Turbinia API - Config router"""

import hashlib
import logging
import os

from datetime import datetime
from fastapi import HTTPException, APIRouter, UploadFile, File, Query
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from typing import List

from turbinia.api.schemas import request_options
from turbinia.api.schemas import evidence as api_evidence
from turbinia import evidence
from turbinia import config as turbinia_config
from turbinia import state_manager

log = logging.getLogger('turbinia')
router = APIRouter(prefix='/evidence', tags=['Turbinia Evidence'])
redis_manager = state_manager.RedisStateManager()


async def upload_file(
    file: UploadFile, file_path: str, calculate_hash: bool = False):
  """Upload file from FastAPI to server.

  Args:
    file (List[UploadFile]): Evidence file to be uploaded to folder for later
        processing. The maximum size of the file is set on the Turbinia
        configuration file. 
  
  Raises:
    IOError: If file is greater than the maximum size.
  
  Returns:
    List of uploaded evidences or warning messages if any.
  """
  size = 0
  sha_hash = hashlib.sha3_224()
  with open(file_path, 'wb') as saved_file:
    while (chunk := await file.read(
        turbinia_config.CHUNK_SIZE)) and size < turbinia_config.MAX_UPLOAD_SIZE:
      saved_file.write(chunk)
      if calculate_hash:
        sha_hash.update(chunk)
      size += turbinia_config.CHUNK_SIZE
      if size >= turbinia_config.MAX_UPLOAD_SIZE:
        error_message = ' '.join((
            f'Unable to upload file {file.filename} greater',
            f'than {turbinia_config.MAX_UPLOAD_SIZE / (1024 ** 3)} GB'))
        log.error(error_message)
        raise IOError(error_message)
    file_info = {
        'Original Name': file.file_name,
        'Saved Name': os.path.basename(file_path),
        'File Path': file_path,
        'Size': size
    }
    if calculate_hash:
      file_info['Hash'] = sha_hash.hexdigest()
  return file_info


@router.get('/types')
async def get_evidence_types(request: Request):
  """Returns supported Evidence object types and required parameters."""
  attribute_mapping = evidence.map_evidence_attributes()
  return JSONResponse(content=attribute_mapping, status_code=200)


@router.get('/types/{evidence_type}')
async def get_evidence_attributes(request: Request, evidence_type):
  """Returns supported Evidence object types and required parameters.
  
  Args:
    evidence_type (str): Name of evidence type.
  """
  attribute_mapping = evidence.map_evidence_attributes()
  attribute_mapping = {evidence_type: attribute_mapping.get(evidence_type)}
  if not attribute_mapping:
    raise HTTPException(
        status_code=404, detail=f'Evidence type ({evidence_type:s}) not found.')
  return JSONResponse(content=attribute_mapping, status_code=200)


@router.get('/summary')
async def get_evidence_summary(request: Request):
  """Retrieves a summary of all evidences in redis.
  
  Raises:
    HTTPException: if there are no evidences.
  """
  evidences = redis_manager.get_evidence_summary()
  if evidences:
    return JSONResponse(
        content=redis_manager.get_evidence_summary(), status_code=200)
  raise HTTPException(status_code=404, detail='No evidences found.')


@router.get('/id')
async def get_evidence_by_id(request: Request, evidence_id):
  """Retrieves an evidence in redis by using its UUID.

  Args:
    evidence_id (str): The UUID of the evidence.
  
  Raises:
    HTTPException: if the evidence is not found.

  Returns:

  """
  if redis_manager.get_evidence(evidence_id):
    return JSONResponse(
        content=redis_manager.get_evidence(evidence_id), status_code=200)
  raise HTTPException(
      status_code=404,
      detail=f'UUID {evidence_id} not found or it had no associated evidences.')


@router.get('/{file_hash}')
async def get_evidence_by_hash(request: Request, file_hash):
  """Retrieves an evidence in redis by using its hash (SHA3-224).

  Args: 
    file_hash (str): SHA3-224 hash of file.
  
  Raises:
    HTTPException: if the evidence is not found.

  Returns:

  """
  if key := redis_manager.get_evidence_key_by_hash(file_hash):
    return JSONResponse(
        content={key: redis_manager.get_evidence_by_hash(file_hash)},
        status_code=200)
  raise HTTPException(
      status_code=404,
      detail=f'Hash {file_hash} not found or it had no associated evidences.')


#todo(igormr) update request_ids for every request
#todo(igormr) Make TurbiniaRequest on redis pointing to TurbiniaEvidence and back
#todo(igormr) Check if turbinia client works with new endpoints, especially upload
#todo(igormr) Make link from evidence to task


@router.post('/upload')
async def upload_evidence(
    request: Request, ticked_id: str, calculate_hash: bool = Query(
        False, choices=(False, True)), files: List[UploadFile] = File(...)):
  """Upload evidence file to server for processing.

  Args:
    file (List[UploadFile]): Evidence file to be uploaded to folder for later
        processing. The maximum size of the file is 10 GB. 
  
  Raises:
    TypeError: If pre-conditions are not met.
  
  Returns:
    List of uploaded evidences or warning messages if any.
  """
  evidences = []
  for file in files:
    file_name = os.path.splitext(file.filename)[0]
    file_extension = os.path.splitext(file.filename)[1]
    file_path = ''.join((
        turbinia_config.OUTPUT_DIR, '/', ticked_id, '/', file_name, '_',
        datetime.now().strftime(
            turbinia_config.DATETIME_FORMAT), file_extension))
    warning_message = None
    try:
      file_info = upload_file(file, file_path, calculate_hash)
    except IOError as exception:
      warning_message = exception
    file.file.close()
    if evidence_key := redis_manager.get_evidence_key_by_hash(
        file_info['hash']):
      warning_message = (
          f'File {file.filename} was uploaded before, check {evidence_key}')
    if warning_message:
      evidences.append(warning_message)
      log.error(warning_message)
      try:
        os.remove(file_path)
      except OSError:
        log.error(f'Could not remove file {file_path}')
    else:
      evidences.append()
  return JSONResponse(content=evidences, status_code=200)
