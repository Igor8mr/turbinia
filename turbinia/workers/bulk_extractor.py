# -*- coding: utf-8 -*-
# Copyright 2019 Google Inc.
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
"""Task for running Bulk Extractor."""

import logging
import os
import xml.etree.ElementTree as xml_tree

from turbinia import TurbiniaException
from turbinia import config
from turbinia.evidence import BulkExtractorOutput
from turbinia.evidence import EvidenceState as state
from turbinia.lib import text_formatter as fmt
from turbinia.workers import TurbiniaTask

log = logging.getLogger('turbinia')

REPORT_FILENAME = "report.md"


class BulkExtractorTask(TurbiniaTask):
  """Task to generate Bulk Extractor output."""

  REQUIRED_STATES = [state.ATTACHED]

  TASK_CONFIG = {
      # These are extra arguments passed when running bulk_extractor
      'bulk_extractor_args': None,
      # List of paths that contain any sort of regex divided by newline. These files must be accessible to the workers.
      'regex_pattern_files': []
  }

  def run(self, evidence, result):
    """Run Bulk Extractor binary.

        Args:
            evidence (Evidence object): The evidence we will process.
            result (TurbiniaTaskResult): The object to place task results into.

        Returns:
            TurbiniaTaskResult object.
        """
    config.LoadConfig()

    # TODO(wyassine): Research whether bulk extractor has an option to
    # generate a summary report to stdout so that it could be used for
    # a report in this task.
    # Create the new Evidence object that will be generated by this Task.
    output_evidence = BulkExtractorOutput()
    # Create a path that we can write the new file to.
    base_name = os.path.basename(evidence.local_path)
    output_file_path = os.path.join(self.output_dir, base_name)
    report_path = os.path.join(self.output_dir, REPORT_FILENAME)
    # Add the output path to the evidence so we can automatically save it
    # later.
    output_evidence.local_path = output_file_path
    output_evidence.uncompressed_directory = output_file_path

    if self.task_config.get('bulk_extractor_args'):
      bulk_extractor_args = self.task_config.get('bulk_extractor_args')
      # Some of bulk_extractors arguments use the '=' character
      # need to substitute with '~' until we have recipes.
      bulk_extractor_args = bulk_extractor_args.replace('~', '=')
      bulk_extractor_args = bulk_extractor_args.split(':')
    else:
      bulk_extractor_args = None

    regex_pattern_file_paths = []
    if self.task_config.get('regex_pattern_files'):
      for regex_pattern_file_path in self.task_config.get(
          'regex_pattern_files'):
        if os.path.exists(regex_pattern_file_path):
          regex_pattern_file_paths.append(regex_pattern_file_path)
      if regex_pattern_file_paths:
        result.log(
            f"{len(regex_pattern_file_paths):} valid Pattern Files detected.")

    try:
      # Generate the command we want to run then execute.
      cmd = ['bulk_extractor']

      # if evidence type is Directory we need to add an -R parameter to the command
      if evidence.type == "Directory" or evidence.type == "CompressedDirectory":
        result.log(
            f"Running Bulk Extractor against {evidence.type:s} by using -R Flag."
        )
        cmd.extend(['-R'])
      cmd.extend(['-o', output_file_path])

      if bulk_extractor_args:
        cmd.extend(bulk_extractor_args)
      if regex_pattern_file_paths:
        for regex_pattern_file_path in regex_pattern_file_paths:
          cmd.extend(['-F', regex_pattern_file_path])

      cmd.append(evidence.local_path)

      result.log(f"Running Bulk Extractor as [{' '.join(cmd):s}]")
      self.execute(cmd, result, new_evidence=[output_evidence])

      # Generate bulk extractor report
      (report, summary) = self.generate_summary_report(output_file_path)
      output_evidence.text_data = report
      result.report_data = output_evidence.text_data

      with open(report_path, 'wb') as fh:
        fh.write(output_evidence.text_data.encode('utf-8'))

      # Compress the bulk extractor output directory.
      output_evidence.compress()
      result.close(self, success=True, status=summary)
    except TurbiniaException as exception:
      result.close(self, success=False, status=str(exception))
      return result
    return result

  def check_xml_attrib(self, xml_key):
    """Checks if a key exists within the xml report.

        Args:
          xml_key(str): the xml key to check for.

        Returns:
          xml_hit(str): the xml value else return N/A.
        """
    xml_hit = 'N/A'
    xml_search = self.xml.find(xml_key)

    # If exists, return the text value.
    if xml_search is not None:
      xml_hit = xml_search.text
    return xml_hit

  def generate_summary_report(self, output_file_path):
    """Generate a summary report from the resulting bulk extractor run.

        Args:
          output_file_path(str): the path to the bulk extractor output.

        Returns:
          tuple: containing:
            report_test(str): The report data
            summary(str): A summary of the report (used for task status)
        """
    findings = []
    features_count = 0
    report_path = os.path.join(output_file_path, 'report.xml')

    # Check if report.xml was not generated by bulk extractor.
    if not os.path.exists(report_path):
      report = 'Execution successful, but the report is not available.'
      return (report, report)

    # Parse existing XML file.
    self.xml = xml_tree.parse(report_path)

    # Place in try/except statement to continue execution when
    # an attribute is not found and NoneType is returned.
    try:
      # Retrieve summary related results.
      findings.append(fmt.heading4('Bulk Extractor Results'))
      findings.append(fmt.heading5('Run Summary'))
      findings.append(
          fmt.bullet(
              'Program: {0} - {1}'.format(
                  self.check_xml_attrib('creator/program'),
                  self.check_xml_attrib('creator/version'))))
      findings.append(
          fmt.bullet(
              'Command Line: {0}'.format(
                  self.check_xml_attrib(
                      'creator/execution_environment/command_line'))))
      findings.append(
          fmt.bullet(
              'Start Time: {0}'.format(
                  self.check_xml_attrib(
                      'creator/execution_environment/start_time'))))
      findings.append(
          fmt.bullet(
              f"Elapsed Time: {self.check_xml_attrib('report/elapsed_seconds')}"
          ))

      # Retrieve results from each of the scanner runs and display in table
      feature_files = self.xml.find(".//feature_files")
      scanner_results = []
      if feature_files is not None:
        findings.append(fmt.heading5('Scanner Results\n'))
        for name, count in zip(self.xml.findall(".//feature_file/name"),
                               self.xml.findall(".//feature_file/count")):
          scanner_results.append({"Name": name.text, "Count": int(count.text)})
          features_count += int(count.text)
        sorted_scanner_results = sorted(
            scanner_results, key=lambda x: x["Count"], reverse=True)
        columns = scanner_results[0].keys()
        findings.append(" | ".join(columns))
        findings.append(" | ".join(["---"] * len(columns)))
        for scanner_result in sorted_scanner_results:
          findings.append(
              " | ".join(str(scanner_result[column]) for column in columns))
      else:
        findings.append(fmt.heading5("There are no findings to report."))
    except AttributeError as exception:
      log.warning(
          f'Error parsing feature from Bulk Extractor report: {exception!s}')
    summary = f'{features_count} artifacts have been extracted.'
    report = '\n'.join(findings)
    return (report, summary)
