#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import yaml
import base64
import json
from flask import Flask, jsonify, render_template, request, Response

from threatcode.conversion.base import Backend
from threatcode.plugins import InstalledThreatcodePlugins
from threatcode.collection import ThreatcodeCollection
from threatcode.exceptions import ThreatcodeError
from threatcode.processing import pipeline
from threatcode.processing.pipeline import ProcessingPipeline

app = Flask(__name__)
plugins = InstalledThreatcodePlugins.autodiscover()
pipeline_generic = pipeline.ProcessingPipeline()
backends = plugins.backends
pipeline_resolver = plugins.get_pipeline_resolver()
pipelines = list(pipeline_resolver.list_pipelines())
pipelines_names = [p[0] for p in pipelines]


@app.route("/")
def home():
    formats = []
    for backend in backends.keys():
        for name, description in plugins.backends[backend].formats.items():
            formats.append(
                {"name": name, "description": description, "backend": backend}
            )

    for name, pipeline in pipelines:
        if len(pipeline.allowed_backends) > 0:
            pipeline.backends = ", ".join(pipeline.allowed_backends)
        else:
            pipeline.backends = "all"

    return render_template(
        "index.html", backends=backends, pipelines=pipelines, formats=formats
    )


@app.route("/getpipelines", methods=["GET"])
def get_pipelines():
    return jsonify(pipelines_names)


@app.route("/threatcode", methods=["POST"])
def convert():
    # get params from request
    rule = str(base64.b64decode(request.json["rule"]), "utf-8")
    # check if input is valid yaml
    try:
        yaml.safe_load(rule)
    except:
        print("error")
        return Response(
            f"YamlError: Malformed yaml file", status=400, mimetype="text/html"
        )

    pipeline = []
    if request.json["pipeline"]:
        for p in request.json["pipeline"]:
            pipeline.append(p)

    template_pipeline = ""
    if request.json["pipelineYml"]:
        try:
            template = str(base64.b64decode(request.json["pipelineYml"]), "utf-8")
            template_pipeline = pipeline_generic.from_yaml(template)
        except:
            return Response(
                f"YamlError: Malformed Pipeline Yaml", status=400, mimetype="text/html"
            )

    target = request.json["target"]
    format = request.json["format"]

    backend_class = backends[target]
    processing_pipeline = pipeline_resolver.resolve(pipeline)

    if isinstance(template_pipeline, ProcessingPipeline):
        processing_pipeline += template_pipeline
    else:
        print("no processing pipeline")

    backend: Backend = backend_class(processing_pipeline=processing_pipeline)

    try:
        threatcode_rule = ThreatcodeCollection.from_yaml(rule)
        result = backend.convert(threatcode_rule, format)
        if isinstance(result, list):
            result = result[0]
    except ThreatcodeError as e:
        return Response(f"ThreatcodeError: {str(e)}", status=400, mimetype="text/html")

    return result


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
