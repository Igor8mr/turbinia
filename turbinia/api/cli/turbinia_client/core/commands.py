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
"""Turbinia API client command-line tool."""

import os
import logging
import click
import base64
import mimetypes
import tarfile

from fastapi import UploadFile

from turbinia_api_lib import exceptions
from turbinia_api_lib import api_client
from turbinia_api_lib.api import turbinia_requests_api
from turbinia_api_lib.api import turbinia_tasks_api
from turbinia_api_lib.api import turbinia_configuration_api
from turbinia_api_lib.api import turbinia_jobs_api
from turbinia_api_lib.api import turbinia_request_results_api
from turbinia_api_lib.api import turbinia_evidence_api

from turbinia_client.core import groups
from turbinia_client.helpers import formatter

from turbinia.processors.mount_local import GetDiskSize
from turbinia.config.turbinia_config_tmpl import MAX_UPLOAD_SIZE

log = logging.getLogger('turbinia')


@groups.config_group.command('list')
@click.pass_context
def get_config(ctx: click.Context) -> None:
  """Gets Turbinia server configuration."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_configuration_api.TurbiniaConfigurationApi(client)
  try:
    api_response = api_instance.read_config()
    formatter.echo_json(api_response)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_config: {exception.body}')


@groups.result_group.command('request')
@click.pass_context
@click.argument('request_id')
def get_request_result(ctx: click.Context, request_id: str) -> None:
  """Gets Turbinia request results / output files."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_request_results_api.TurbiniaRequestResultsApi(client)
  try:
    api_response = api_instance.get_request_output(
        request_id, _preload_content=False, _request_timeout=(30, 30))
    filename = f'{request_id}.tgz'
    click.echo(f'Saving output for request {request_id} to: {filename}')
    # Read the response and save into a local file.
    with open(filename, 'wb') as file:
      for chunk in api_response.read_chunked():
        file.write(chunk)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_request_output: {exception.body}')
  except OSError as exception:
    log.error(f'Unable to save file: {exception}')
  except (ValueError, tarfile.ReadError, tarfile.CompressionError) as exception:
    log.error(f'Error reading saved results file {filename}: {exception}')


@groups.result_group.command('task')
@click.pass_context
@click.argument('task_id')
def get_task_result(ctx: click.Context, task_id: str) -> None:
  """Gets Turbinia task results / output files."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_request_results_api.TurbiniaRequestResultsApi(client)
  try:
    api_response = api_instance.get_task_output(
        task_id, _preload_content=False, _request_timeout=(30, 30))
    filename = f'{task_id}.tgz'
    click.echo(f'Saving output for task {task_id} to: {filename}')

    # Read the response and save into a local file.
    with open(filename, 'wb') as file:
      for chunk in api_response.read_chunked():
        file.write(chunk)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_task_output: {exception.body}')
  except OSError as exception:
    log.error(f'Unable to save file: {exception}')
  except (ValueError, tarfile.ReadError, tarfile.CompressionError) as exception:
    log.error(f'Error reading saved results file {filename}: {exception}')


@groups.jobs_group.command('list')
@click.pass_context
def get_jobs(ctx: click.Context) -> None:
  """Gets Turbinia jobs list."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_jobs_api.TurbiniaJobsApi(client)
  try:
    api_response = api_instance.read_jobs()
    click.echo(api_response)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling read_jobs: {exception.body}')


@groups.status_group.command('request')
@click.pass_context
@click.argument('request_id')
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_request(ctx: click.Context, request_id: str, json_dump: bool) -> None:
  """Gets Turbinia request status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_requests_api.TurbiniaRequestsApi(client)
  if request_id == 'summary':
    click.echo(
        'Oops! "summary" is not a valid request identifier. '
        'Did you mean to run "turbinia-client status summary" instead?')
    return
  try:
    api_response = api_instance.get_request_status(request_id)
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.RequestMarkdownReport(api_response).generate_markdown()
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_request_status: {exception.body}')


@groups.status_group.command('workers')
@click.pass_context
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_workers(ctx: click.Context, json_dump: bool) -> None:
  click.echo('Not implemented yet.')


@groups.status_group.command('summary')
@click.pass_context
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_requests_summary(ctx: click.Context, json_dump: bool) -> None:
  """Gets a summary of all Turbinia requests."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_requests_api.TurbiniaRequestsApi(client)
  try:
    api_response = api_instance.get_requests_summary()
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.SummaryMarkdownReport(api_response).generate_markdown()
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_requests_summary: {exception.body}')


@groups.status_group.command('task')
@click.pass_context
@click.argument('task_id')
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_task(ctx: click.Context, task_id: str, json_dump: bool) -> None:
  """Gets Turbinia task status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_tasks_api.TurbiniaTasksApi(client)
  try:
    api_response = api_instance.get_task_status(task_id)
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.TaskMarkdownReport(api_response).generate_markdown()
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_task_status: {exception.body}')


@click.pass_context
def create_request(ctx: click.Context, *args: int, **kwargs: int) -> None:
  """Creates and submits a new Turbinia request."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_requests_api.TurbiniaRequestsApi(client)
  evidence_name = ctx.command.name

  # Normalize the evidence class name from lowercase to the original name.
  evidence_name = ctx.obj.normalize_evidence_name(evidence_name)
  # Build request and request_options objects to send to the API server.
  request_options = list(ctx.obj.request_options.keys())
  request = {'evidence': {'type': evidence_name}, 'request_options': {}}

  if 'googlecloud' in evidence_name:
    api_instance_config = turbinia_configuration_api.TurbiniaConfigurationApi(
        client)
    cloud_provider = api_instance_config.read_config()['CLOUD_PROVIDER']
    if cloud_provider != 'GCP':
      log.error(
          f'The evidence type {evidence_name} is Google Cloud only and '
          f'the configured provider for this Turbinia instance is '
          f'{cloud_provider}.')
      return

  for key, value in kwargs.items():
    # If the value is not empty, add it to the request.
    if kwargs.get(key):
      # Check if the key is for evidence or request_options
      if not key in request_options:
        request['evidence'][key] = value
      elif key in ('jobs_allowlist', 'jobs_denylist'):
        jobs_list = value.split(',')
        request['request_options'][key] = jobs_list
      else:
        request['request_options'][key] = value

  if all(key in request['request_options']
         for key in ('recipe_name', 'recipe_data')):
    log.error('You can only provide one of recipe_data or recipe_name')
    return

  recipe_name = request['request_options'].get('recipe_name')
  if recipe_name:
    if not recipe_name.endswith('.yaml'):
      recipe_name = f'{recipe_name}.yaml'
    # Fallback path for the recipe would be TURBINIA_CLI_CONFIG_PATH/recipe_name
    # This is the same path where the client configuration is loaded from.
    recipe_path_fallback = os.path.expanduser(ctx.obj.config_path)
    recipe_path_fallback = os.path.join(recipe_path_fallback, recipe_name)

    if os.path.isfile(recipe_name):
      recipe_path = recipe_name
    elif os.path.isfile(recipe_path_fallback):
      recipe_path = recipe_path_fallback
    else:
      log.error(f'Unable to load recipe {recipe_name}.')
      return

    try:
      with open(recipe_path, 'r', encoding='utf-8') as recipe_file:
        # Read the file and convert to base64 encoded bytes.
        recipe_bytes = recipe_file.read().encode('utf-8')
        recipe_data = base64.b64encode(recipe_bytes)
    except OSError as exception:
      log.error(f'Error opening recipe file {recipe_path}: {exception}')
      return
    except TypeError as exception:
      log.error(f'Error converting recipe data to Base64: {exception}')
      return
    # We found the recipe file, so we will send it to the API server
    # via the recipe_data parameter. To do so, we need to pop recipe_name
    # from the request so that we only have recipe_data.
    request['request_options'].pop('recipe_name')
    # recipe_data should be a UTF-8 encoded string.
    request['request_options']['recipe_data'] = recipe_data.decode('utf-8')

  # Send the request to the API server.
  try:
    log.info(f'Sending request: {request}')
    api_response = api_instance.create_request(request)
    log.info(f'Received response: {api_response}')
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling create_request: {exception.body}')
  except (TypeError, exceptions.ApiTypeError) as exception:
    log.error(f'The request object is invalid. {exception}')


@groups.evidence_group.command('summary')
@click.pass_context
@click.option(
    '--sort', '-s', help='Attribute by which output will be sort.',
    required=False)
@click.option(
    '--values', '-v', help='Outputs values.', is_flag=True, required=False)
@click.option(
    '--count', '-c', help='Outputs count.', is_flag=True, required=False)
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_evidence_summary(
    ctx: click.Context, sort: str = None, values: bool = False,
    count: bool = False, json_dump: bool = False) -> None:
  """Gets Turbinia evidence status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_evidence_api.TurbiniaEvidenceApi(client)
  try:
    output = 'values' if values else 'count' if count else 'keys'
    api_response = api_instance.get_evidence_summary(sort, output)
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.EvidenceSummaryMarkdownReport(
          api_response).generate_summary_markdown(output)
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_evidence_summary: {exception.body}')


@groups.evidence_group.command('query')
@click.pass_context
@click.argument('attribute')
@click.argument('value')
@click.option(
    '--values', '-v', help='Outputs values.', is_flag=True, required=False)
@click.option(
    '--count', '-c', help='Outputs count.', is_flag=True, required=False)
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def query_evidence(
    ctx: click.Context, attribute: str, value: str, values: bool, count: bool,
    json_dump: bool) -> None:
  """Gets Turbinia task status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_evidence_api.TurbiniaEvidenceApi(client)
  try:
    output = 'values' if values else 'count' if count else 'keys'
    api_response = api_instance.query_evidence(value, attribute, output)
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.EvidenceSummaryMarkdownReport(
          api_response).generate_summary_markdown(output)
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_task_status: {exception.body}')


@groups.evidence_group.command('get')
@click.pass_context
@click.argument('evidence_id')
@click.option(
    '--show_ignored', '-i', help='Shows ignored evidence attributes.',
    is_flag=True, required=False)
@click.option(
    '--show_null', '-n', help='Shows evidence attributes with null value.',
    is_flag=True, required=False)
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def get_evidence(
    ctx: click.Context, evidence_id: str, show_ignored: bool, show_null: bool,
    json_dump: bool) -> None:
  """Gets Turbinia evidence status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_evidence_api.TurbiniaEvidenceApi(client)
  try:
    api_response = api_instance.get_evidence_by_id(evidence_id)
    if json_dump:
      formatter.echo_json(api_response)
    else:
      report = formatter.EvidenceMarkdownReport(api_response).generate_markdown(
          1, show_ignored, show_null)
      click.echo(report)
  except exceptions.ApiException as exception:
    log.error(
        f'Received status code {exception.status} '
        f'when calling get_evidence: {exception.body}')


@groups.evidence_group.command('upload')
@click.pass_context
@click.argument('ticket_id')
@click.option(
    '--file', '-f', help='Path of file to be uploaded.', required=False,
    multiple=True)
@click.option(
    '--directory', '-d', help=(
        'Path of directory of files to be uploaded '
        '(does not include files in subfolders).'), required=False,
    multiple=True)
@click.option(
    '--calculate_hash', '-c', help='Calculates file hash.', is_flag=True,
    required=False)
@click.option(
    '--json_dump', '-j', help='Generates JSON output.', is_flag=True,
    required=False)
def upload_evidence(
    ctx: click.Context, ticket_id: str, file: list, directory: list,
    calculate_hash: bool, json_dump: bool) -> None:
  """Gets Turbinia evidence status."""
  client: api_client.ApiClient = ctx.obj.api_client
  api_instance = turbinia_evidence_api.TurbiniaEvidenceApi(client)
  all_files = list(file)
  for current_directory in directory:
    for file_name in os.listdir(current_directory):
      file_path = os.path.join(current_directory, file_name)
      if os.path.isfile(file_path):
        all_files.append(file_path)
  report = {}
  for file_path in all_files:
    try:
      size = os.path.getsize(file_path)
      if size > MAX_UPLOAD_SIZE:
        error_message = (
            f'Unable to upload {size / (1024 ** 3)} GB file',
            f'{file_path} greater than {MAX_UPLOAD_SIZE / (1024 ** 3)} GB')
        log.error(error_message)
        continue
      abs_path = os.path.abspath(file_path)
      with open(file_path, 'rb') as f:
        filename = os.path.basename(f.name)
        filedata = f.read()
        mimetype = (
            mimetypes.guess_type(filename)[0] or 'application/octet-stream')
        upload_file = tuple([filename, filedata, mimetype])
    except OSError:
      log.error(f'Unable to read file in {file_path}')
      continue
    try:
      api_response = api_instance.upload_evidence(
          upload_file, ticket_id, calculate_hash)
      report[abs_path] = api_response
    except exceptions.ApiException as exception:
      error_message = (
          f'Received status code {exception.status} '
          f'when calling upload_evidence: {exception}')
      log.error(error_message)
      report[abs_path] = error_message
  if json_dump:
    formatter.echo_json(report)
  else:
    report = '\n'.join(
        formatter.EvidenceMarkdownReport({}).dict_to_markdown(
            report, format_name=False))
    click.echo(report)