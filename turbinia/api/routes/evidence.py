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

from fastapi import HTTPException, APIRouter, UploadFile, File
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from typing import List

from turbinia.api.schemas import request_options
from turbinia.api.schemas import evidence as api_evidence
from turbinia import evidence
from turbinia import config as turbinia_config
from turbinia import client as TurbiniaClientProvider

log = logging.getLogger('turbinia')
router = APIRouter(prefix='/evidence', tags=['Turbinia Evidence'])
client = TurbiniaClientProvider.get_turbinia_client()


@router.get('/types')
async def get_evidence_types(request: Request):
  """Returns supported Evidence object types and required parameters."""
  attribute_mapping = evidence.map_evidence_attributes()
  return JSONResponse(content=attribute_mapping, status_code=200)


@router.get('/types/{evidence_type}')
async def get_evidence_attributes_by_type(request: Request, evidence_type):
  """Returns supported Evidence object types and required parameters."""
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
  evidences = client.redis.get_evidence_summary()
  if evidences:
    return client.redis.get_evidence_summary()
  raise HTTPException(status_code=404, detail='No evidences found.')


@router.get('/{file_hash}')
async def get_evidence_by_hash(request: Request, file_hash):
  """Retrieves an evidence in redis by its hash (SHA3-224).
  Args:
    file_hash (str): SHA3-224 hash of file
  Raises:
    HTTPException: if the evidence is not found.
  """
  if client.redis.get_evidence(file_hash):
    return client.redis.get_evidence(file_hash)
  else:
    raise HTTPException(
        status_code=404,
        detail=f'Hash {file_hash} not found or it had no associated evidences.')


#todo(igormr) add max file length
#todo(igormr) update request_ids for every request
#todo(igormr) Make TurbiniaRequest on redis pointing to TurbiniaEvidence and back


@router.post('/upload')
async def upload_evidence(
    request: Request, information: List[api_evidence.Evidence],
    files: List[UploadFile] = File(...)):
  """Upload evidence file to the OUTPUT_DIR folder for processing.
  Args:
    file: Evidence file to be uploaded to evidences folder for later
        processing. The maximum size of the file is 10 GB. 
    name: The name with which the file will be saved. It is necessary to
        include the extension of the file. The name cannot be equal to that
        of an existent file.
    evidence_type: The type of the 
  Raises:
    HTTPException: If pre-conditions are not met.
  """
  # Extracts nested list
  information = information[0]
  if len(files) != len(information):
    log.error(f'Wrong number of arguments: {TypeError}')
    raise TypeError('Wrong number of arguments')
  evidences = []
  separator = '' if turbinia_config.TMP_DIR[-1] == '/' else '/'
  for i in range(len(files)):
    name = information[i].name
    file_path = separator.join([turbinia_config.TMP_DIR, name])
    equal_files = 1
    while os.path.exists(file_path):
      equal_files += 1
      name = f'({equal_files} {information[i].name})'
      file_path = separator.join([turbinia_config.TMP_DIR, name])
    with open(file_path, 'wb') as saved_file:
      sha_hash = hashlib.sha3_224()
      while chunk := await files[i].read(1024):
        saved_file.write(chunk)
        sha_hash.update(chunk)
      file_hash = sha_hash.hexdigest()
    files[i].file.close()
    if client.redis.get_evidence(file_hash):
      message = ', '.join((
          f'File {information[i].name} was uploaded before',
          f'check TurbiniaEvidence:{file_hash}'))
      evidences.append([message])
      log.error(message)
      try:
        os.remove(file_path)
      except OSError:
        log.error(f'Could not remove duplicate file {file_path}')
    else:
      evidence_ = evidence.create_evidence(
          evidence_type=information[i].evidence_type.lower(),
          source_path=file_path, browser_type=information[i].browser_type,
          disk_name=information[i].disk_name,
          embedded_path=information[i].embedded_path,
          format=information[i].format,
          mount_partition=information[i].mount_partition,
          name=information[i].name, profile=information[i].profile,
          project=information[i].project, source=information[i].source,
          zone=information[i].zone, file_hash=file_hash)
      key = client.redis.write_new_evidence(evidence_)
      evidences.append((key, evidence_.serialize()))
  return evidences
