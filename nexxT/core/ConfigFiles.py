# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This modules defines classes for nexxT config file handling.
"""

import copy
import json
import logging
from pathlib import Path
from jsonschema import Draft7Validator, validators

logger = logging.getLogger(__name__)

class ConfigFileLoader:
    """
    Class for loading configurations from disk using a json format along with an appropriate schema.
    """
    _validator = None
    _validatorGuiState = None

    @staticmethod
    def load(config, file):
        """
        Load configuration from file.
        :param file: string or Path instance
        :param config: Configuration instance to be populated
        :return: dictionary with configuration contents (default values from schema are already applied)
        """
        validator, validatorGuiState = ConfigFileLoader._getValidator()
        if not isinstance(file, Path):
            file = Path(file)
        with file.open("r", encoding='utf-8') as fp:
            cfg = json.load(fp)
        validator.validate(cfg)
        guistateFile = file.parent / (file.name + ".guistate")
        if guistateFile.exists():
            try:
                with guistateFile.open("r", encoding="utf-8") as fp:
                    guistate = json.load(fp)
                validatorGuiState.validate(guistate)
            except Exception as e: # pylint: disable=broad-except
                # catching a broad exception is exactly wanted here.
                logger.warning("ignoring error while loading %s: %s", guistateFile, e)
                guistate = None
        else:
            logger.info("no gui state file for config, using default values from original file.")
            guistate = None
        cfg["CFGFILE"] = str(file.absolute())
        if not guistate is None:
            cfg = ConfigFileLoader._merge(cfg, guistate)
        config.load(cfg)
        return config

    @staticmethod
    def save(config, file=None, forceGuiState=False):
        """
        Save the configuration to the given file (or overwrite the existing file).
        :param config: A Configuration instance
        :param file: a file given as string or Path
        :return: None
        """
        # TODO: saving to new file will eventually destroy relative paths.
        cfg = config.save(file)
        if file is None:
            file = cfg["CFGFILE"]
        del cfg["CFGFILE"]

        validator, validatorGuiState = ConfigFileLoader._getValidator()
        validator.validate(cfg)
        if not isinstance(file, Path):
            file = Path(file)
        oldCfg = None
        if file.exists():
            try:
                with file.open("r", encoding="utf-8") as fp:
                    oldCfg = json.load(fp)
                    validator.validate(oldCfg)
            except Exception: # pylint: disable=broad-except
                # catching a broad exception is exactly wanted here
                oldCfg = None
        if oldCfg is not None:
            cfgWithOldGuiState, guistate = ConfigFileLoader._split(cfg, oldCfg)
            if not forceGuiState:
                cfg = cfgWithOldGuiState
            validatorGuiState.validate(guistate)
        else:
            guistate = None

        if "_guiState" in cfg and "PlaybackControl_folder" in cfg["_guiState"]:
            del cfg["_guiState"]["PlaybackControl_folder"]
        if "_guiState" in cfg and "PlaybackControl_recent" in cfg["_guiState"]:
            del cfg["_guiState"]["PlaybackControl_recent"]
        if "_guiState" in cfg and "RecordingControl_directory" in cfg["_guiState"]:
            del cfg["_guiState"]["RecordingControl_directory"]

        with file.open("w", encoding='utf-8') as fp:
            json.dump(cfg, fp, indent=2, ensure_ascii=False)
        if guistate is not None:
            guistateFile = file.parent / (file.name + ".guistate")
            with guistateFile.open("w", encoding="utf-8") as fp:
                json.dump(guistate, fp, indent=2, ensure_ascii=False)

    @staticmethod
    def saveGuiState(config):
        """
        save the gui state related to config (doesn't touch the original config file)
        :param config: a Configuration instance
        :return: None
        """
        validator, validatorGuiState = ConfigFileLoader._getValidator()
        cfg = config.save()
        file = cfg["CFGFILE"]
        if file is None:
            return
        if not isinstance(file, Path):
            file = Path(file)
        oldCfg = None
        # first, read original cfg file contents
        if file.exists():
            try:
                with file.open("r", encoding="utf-8") as fp:
                    oldCfg = json.load(fp)
                    validator.validate(oldCfg)
            except Exception: # pylint: disable=broad-except
                # catching a general exception is exactly wanted here
                oldCfg = None
        if oldCfg is None:
            return
        _, guistate = ConfigFileLoader._split(cfg, oldCfg)
        validatorGuiState.validate(guistate)
        guistateFile = file.parent / (file.name + ".guistate")
        with guistateFile.open("w", encoding="utf-8") as fp:
            json.dump(guistate, fp, indent=2, ensure_ascii=False)

    @staticmethod
    def _extendWithDefault(validatorClass):
        """
        see https://python-jsonschema.readthedocs.io/en/stable/faq/
        :param validator_class:
        :return:
        """
        validate_properties = validatorClass.VALIDATORS["properties"]
        def setDefaults(validator, properties, instance, schema):
            for jsonProperty, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(jsonProperty, subschema["default"])
            for error in validate_properties(validator, properties, instance, schema):
                yield error
        return validators.extend(
            validatorClass, {"properties": setDefaults},
        )

    @staticmethod
    def _getValidator():
        if ConfigFileLoader._validator is None:
            with (Path(__file__).parent / "ConfigFileSchema.json").open("rb") as fp:
                schema = json.load(fp)
                ConfigFileLoader._validator = ConfigFileLoader._extendWithDefault(Draft7Validator)(schema)
        if ConfigFileLoader._validatorGuiState is None:
            with (Path(__file__).parent / "GuiStateSchema.json").open("rb") as fp:
                schema = json.load(fp)
                ConfigFileLoader._validatorGuiState = ConfigFileLoader._extendWithDefault(Draft7Validator)(schema)
        return ConfigFileLoader._validator, ConfigFileLoader._validatorGuiState

    @staticmethod
    def _merge(cfg, guistate):

        def mergeGuiStateSection(gsCfg, gsGuiState):
            res = gsCfg.copy()
            # merge two gui state sections
            for p in gsGuiState:
                res[p] = gsGuiState[p]
            return res

        def findNamedItemInList(name, listOfItems):
            for item in listOfItems:
                if item["name"] == name:
                    return item
            return None

        cfg["_guiState"] = mergeGuiStateSection(cfg["_guiState"], guistate["_guiState"])
        for subgraphType in ["applications"]:

            for cf in cfg[subgraphType]:
                cfGS = findNamedItemInList(cf["name"], guistate[subgraphType])
                if cfGS is None:
                    continue
                cf["_guiState"] = mergeGuiStateSection(cf["_guiState"], cfGS["_guiState"])

        return cfg

    @staticmethod
    def _split(newCfg, oldCfg):
        """
        returns cfg, guistate such that the gui state in cfg is preserved
        :param newCfg: current config state as returned form Configuration.save(...)
        :param oldCfg: values read from current file
        :return: cfg, guistate
        """

        def findNamedItemInList(name, listOfItems):
            for item in listOfItems:
                if item["name"] == name:
                    return item
            return None

        def splitCommonGuiStateSections(newGuiState, oldGuiState):
            res = newGuiState.copy()
            for p in oldGuiState:
                if p in newGuiState and oldGuiState[p] != newGuiState[p]:
                    newGuiState[p] = oldGuiState[p]
            return res

        guistate = {}
        cfg = copy.deepcopy(newCfg)
        guistate["_guiState"] = splitCommonGuiStateSections(cfg["_guiState"], oldCfg["_guiState"])
        cfg["_guiState"] = oldCfg["_guiState"]

        for subgraphType in ["applications"]:
            guistate[subgraphType] = []
            for cf in cfg[subgraphType]:
                guistate[subgraphType].append(dict(name=cf["name"]))
                cfOld = findNamedItemInList(cf["name"], oldCfg[subgraphType])
                guistate[subgraphType][-1]["_guiState"] = \
                    splitCommonGuiStateSections(cf["_guiState"], cfOld["_guiState"] if cfOld is not None else {})
        return cfg, guistate
