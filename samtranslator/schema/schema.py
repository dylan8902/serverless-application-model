from __future__ import annotations

import argparse
import json
from pathlib import Path

import pydantic

from typing import Any, Dict, Type, Optional, Union


from samtranslator.schema.common import BaseModel, LenientBaseModel
from samtranslator.schema import (
    aws_serverless_simpletable,
    aws_serverless_application,
    aws_serverless_connector,
    aws_serverless_function,
    aws_serverless_statemachine,
    aws_serverless_layerversion,
    aws_serverless_api,
    aws_serverless_httpapi,
    any_cfn_resource,
)


class Globals(BaseModel):
    Function: Optional[aws_serverless_function.Globals]
    Api: Optional[aws_serverless_api.Globals]
    HttpApi: Optional[aws_serverless_httpapi.Globals]
    SimpleTable: Optional[aws_serverless_simpletable.Globals]


Resources = Union[
    aws_serverless_connector.Resource,
    aws_serverless_function.Resource,
    aws_serverless_simpletable.Resource,
    aws_serverless_statemachine.Resource,
    aws_serverless_layerversion.Resource,
    aws_serverless_api.Resource,
    aws_serverless_httpapi.Resource,
    aws_serverless_application.Resource,
]


class _ModelWithoutResources(LenientBaseModel):
    Globals: Optional[Globals]


class SamModel(_ModelWithoutResources):
    Resources: Dict[
        str,
        Union[
            Resources,
            # Ignore resources that are not AWS::Serverless::*
            any_cfn_resource.Resource,
        ],
    ]


class Model(_ModelWithoutResources):
    Resources: Dict[str, Resources]


def get_schema(model: Type[pydantic.BaseModel]) -> Dict[str, Any]:
    obj = model.schema()

    # http://json-schema.org/understanding-json-schema/reference/schema.html#schema
    # https://github.com/pydantic/pydantic/issues/1478
    # Validated in https://github.com/aws/serverless-application-model/blob/5c82f5d2ae95adabc9827398fba8ccfc3dbe101a/tests/schema/test_validate_schema.py#L91
    obj["$schema"] = "http://json-schema.org/draft-04/schema#"

    return obj


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def extend_with_cfn_schema(sam_schema: Dict[str, Any], cfn_schema: Dict[str, Any]) -> None:
    """
    Add CloudFormation resources and template syntax to SAM schema.
    """

    sam_defs = sam_schema["definitions"]
    cfn_defs = cfn_schema["definitions"]

    sam_props = sam_schema["properties"]
    cfn_props = cfn_schema["properties"]

    # Add Resources from CloudFormation schema to SAM schema
    cfn_resources = cfn_props["Resources"]["patternProperties"]["^[a-zA-Z0-9]+$"]["anyOf"]
    sam_props["Resources"]["additionalProperties"]["anyOf"].extend(cfn_resources)

    # Add any other top-level properties from CloudFormation schema to SAM schema
    for k in cfn_props.keys():
        if k not in sam_props:
            sam_props[k] = cfn_props[k]

    # Add definitions from CloudFormation schema to SAM schema
    for k in cfn_defs.keys():
        if k in sam_defs:
            raise Exception(f"Key {k} already in SAM schema definitions")
        sam_defs[k] = cfn_defs[k]

    # The unified schema should include all supported properties
    sam_schema["additionalProperties"] = False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfn-schema", help="input CloudFormation schema", type=Path, required=True)
    parser.add_argument("--sam-schema", help="output SAM schema", type=Path, required=True)
    parser.add_argument("--unified-schema", help="output unified schema", type=Path, required=True)
    args = parser.parse_args()

    sam_schema = get_schema(SamModel)
    args.sam_schema.write_text(json_dumps(sam_schema))

    unified_schema = get_schema(Model)
    cfn_schema = json.loads(args.cfn_schema.read_text())
    extend_with_cfn_schema(unified_schema, cfn_schema)
    args.unified_schema.write_text(json_dumps(unified_schema))


if __name__ == "__main__":
    main()
