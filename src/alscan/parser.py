# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import gzip
import io
import math
from pathlib import Path, PurePath

from lxml import etree

_SAFE_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    recover=False,
)

from alscan.models import Clip, Device, PluginRef, Project, SampleRef, Track

TRACK_TAGS = {
    "AudioTrack": "audio",
    "MidiTrack": "midi",
    "GroupTrack": "group",
    "ReturnTrack": "return",
}

BUILTIN_DEVICE_TAGS = {
    "Eq8", "Compressor2", "Limiter", "Reverb", "StereoGain",
    "AutoFilter", "Delay", "GlueCompressor", "Operator", "Simpler",
    "Sampler", "InstrumentRack", "DrumGroup", "Spectrum", "Tuner",
    "Gate", "Phaser", "Flanger", "Chorus", "Pedal", "Amp",
}


def parse_als(path: str | Path) -> Project:
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        buf = io.BytesIO(raw)
        with gzip.GzipFile(fileobj=buf) as gz:
            xml_bytes = gz.read()
    else:
        xml_bytes = raw
    root = etree.fromstring(xml_bytes, parser=_SAFE_PARSER)
    return _parse_root(root, path)


def parse_xml_string(xml: str, path: str = ".") -> Project:
    root = etree.fromstring(xml.encode("utf-8"), parser=_SAFE_PARSER)
    return _parse_root(root, Path(path))


def _parse_root(root, als_path: Path) -> Project:
    creator = root.get("Creator", "")
    major = root.get("MajorVersion", "")
    minor = root.get("MinorVersion", "")
    live_set = root.find("LiveSet")
    if live_set is None:
        raise ValueError("No <LiveSet> found")
    proj = Project(
        path=als_path.parent, file_path=als_path,
        creator=creator, major_version=major, minor_version=minor,
    )
    _parse_tempo(live_set, proj)
    _parse_time_signature(live_set, proj)
    _parse_locators(live_set, proj)
    _parse_tracks(live_set, proj)
    return proj


def _gv(element, subpath, attr="Value", default=None):
    if element is None:
        return default
    el = element.find(subpath)
    if el is None:
        return default
    return el.get(attr, default)


def _parse_tempo(live_set, proj):
    tempo_el = live_set.find("Tempo")
    if tempo_el is None:
        tempo_el = live_set.find("MainTrack/DeviceChain/Mixer/Tempo")
    if tempo_el is None:
        tempo_el = live_set.find("MasterTrack/MasterChain/Mixer/Tempo")
    if tempo_el is not None:
        manual = tempo_el.find("Manual")
        if manual is not None:
            try:
                proj.tempo = float(manual.get("Value", 120))
            except (ValueError, TypeError):
                pass
        else:
            fe = tempo_el.find("ArrangerAutomation/Events/FloatEvent")
            if fe is not None:
                try:
                    proj.tempo = float(fe.get("Value", 120))
                except (ValueError, TypeError):
                    pass


def _parse_time_signature(live_set, proj):
    ts = live_set.find("TimeSignature")
    if ts is None:
        return
    tss = ts.find("TimeSignatures")
    if tss is None:
        return
    rts = tss.find("RemoteableTimeSignature")
    if rts is None:
        return
    num = rts.find("Numerator")
    den = rts.find("Denominator")
    if num is not None and den is not None:
        n = int(num.get("Value", 4))
        d = int(den.get("Value", 4))
        proj.time_signature = (n, d)


def _parse_locators(live_set, proj):
    loc_outer = live_set.find("Locators")
    if loc_outer is None:
        return
    loc_inner = loc_outer.find("Locators")
    if loc_inner is None:
        return
    for loc in loc_inner.findall("Locator"):
        name = _gv(loc, "Name/EffectiveName", "Value", "")
        time_str = _gv(loc, "Time", "Value", "0")
        try:
            time_val = float(time_str)
        except ValueError:
            time_val = 0.0
        proj.locators.append({"name": name, "time": time_val})


def _parse_tracks(live_set, proj):
    tracks_el = live_set.find("Tracks")
    if tracks_el is None:
        return
    for child in tracks_el:
        local = child.tag if isinstance(child.tag, str) else ""
        track_type = TRACK_TAGS.get(local)
        if track_type is None:
            if local in ("MasterTrack", "MainTrack", "PreHearTrack"):
                track_type = "master"
            else:
                continue
        try:
            track_id = int(child.get("Id", "-1"))
        except ValueError:
            track_id = -1
        name = _gv(child, "Name/EffectiveName", "Value", "")
        color_str = _gv(child, "Color", "Value", None)
        if color_str is None:
            color_str = _gv(child, "ColorIndex", "Value", "0")
        try:
            color_index = int(color_str)
        except ValueError:
            color_index = 0
        frozen = _gv(child, "Freeze", "Value", "false") == "true"
        group_str = _gv(child, "TrackGroupId", "Value", "-1")
        try:
            group_id = int(group_str)
        except ValueError:
            group_id = -1
        track = Track(
            name=name, track_id=track_id, track_type=track_type,
            color_index=color_index, is_frozen=frozen, group_id=group_id,
        )
        _parse_devices(child, track)
        _parse_clips(child, track)
        _parse_mixer(child, track)
        proj.tracks.append(track)
    proj.tracks.sort(key=lambda t: t.track_id)


def _parse_devices(track_el, track):
    device_chain = track_el.find("DeviceChain")
    if device_chain is None:
        return
    devices_el = device_chain.find("Devices")
    if devices_el is None:
        return
    for dev_el in devices_el:
        tag = dev_el.tag if isinstance(dev_el.tag, str) else ""
        if not tag:
            continue
        if tag == "PluginDevice":
            plugin = _parse_plugin(dev_el)
            dev_name = plugin.name if plugin else tag
            track.devices.append(Device(name=dev_name, device_type="plugin", plugin_ref=plugin))
        elif tag in BUILTIN_DEVICE_TAGS:
            dev_name = _gv(dev_el, "PresetRef/Value", "Value", "") or tag
            params = _extract_device_params(dev_el)
            track.devices.append(Device(name=dev_name, device_type=tag, params=params))
        else:
            track.devices.append(Device(name=tag, device_type=tag))


def _parse_plugin(dev_el):
    plugin_desc = dev_el.find("PluginDesc")
    if plugin_desc is None:
        return None
    for info in plugin_desc:
        if info.tag is None:
            continue
        tag = info.tag if isinstance(info.tag, str) else ""
        name = _gv(info, "Name", "Value", "")
        path = ""
        if tag == "VstPluginInfo":
            path = _gv(info, "Path", "Value", "")
            uid = _gv(info, "UniqueId", "Value", "")
            return PluginRef(name=name, plugin_type="vst2", path=path, unique_id=uid)
        elif tag == "Vst3PluginInfo":
            uid = _gv(info, "PluginId", "Value", "")
            version = _gv(info, "PluginVersion", "Value", "")
            return PluginRef(name=name, plugin_type="vst3", path=path, unique_id=uid, version=version)
        elif tag == "AuPluginInfo":
            mfr = _gv(info, "Manufacturer", "Value", "")
            return PluginRef(name=name, plugin_type="au", path=path, manufacturer=mfr)
    return None


def _extract_device_params(dev_el) -> dict[str, object]:
    params: dict[str, object] = {}
    for at in dev_el.findall("AutomationTarget"):
        target = at.find("Target")
        if target is None:
            continue
        name_el = target.find("Name")
        if name_el is not None and name_el.get("Value") == "Device On":
            manual = at.find("Manual")
            if manual is not None:
                v = manual.get("Value", "true")
                params["device_on"] = v.lower() == "true"
        user_name = target.find("UserName")
        if user_name is not None:
            param_name = user_name.get("Value", "")
            manual = at.find("Manual")
            if manual is not None and param_name:
                v = manual.get("Value", "")
                try:
                    params[param_name] = float(v)
                except (ValueError, TypeError):
                    params[param_name] = v
    return params


def _parse_clips(track_el, track):
    device_chain = track_el.find("DeviceChain")
    if device_chain is None:
        return
    seq = device_chain.find("MainSequencer")
    if seq is None:
        return
    slot_list = seq.find("ClipSlotList")
    if slot_list is None:
        return
    for slot_el in slot_list.findall("ClipSlot"):
        # Ableton nests ClipSlot: outer has HasStop, inner has Value
        inner = slot_el.find("ClipSlot")
        slot = inner if inner is not None else slot_el
        value_el = slot.find("Value")
        if value_el is None:
            continue
        for clip_el in value_el:
            if clip_el.tag is None:
                continue
            tag = clip_el.tag if isinstance(clip_el.tag, str) else ""
            if tag == "AudioClip":
                clip = _parse_audio_clip(clip_el)
                if clip:
                    track.clips.append(clip)
            elif tag == "MidiClip":
                clip = _parse_midi_clip(clip_el)
                if clip:
                    track.clips.append(clip)


def _parse_audio_clip(el):
    name = _gv(el, "Name", "Value", "")
    color_str = _gv(el, "ColorIndex", "Value", "0")
    try:
        color_index = int(color_str)
    except ValueError:
        color_index = 0
    time_str = el.get("Time", "0")
    try:
        start_time = float(time_str)
    except ValueError:
        start_time = 0.0
    is_warped = _gv(el, "IsWarped", "Value", "false") == "true"
    warp_str = _gv(el, "WarpMode", "Value", "0")
    try:
        warp_mode = int(warp_str)
    except ValueError:
        warp_mode = 0
    loop = el.find("Loop")
    duration = 0.0
    loop_on = False
    if loop is not None:
        end_str = _gv(loop, "LoopEnd", "Value", "0")
        try:
            duration = float(end_str)
        except ValueError:
            pass
        loop_on = _gv(loop, "LoopOn", "Value", "false") == "true"
    sample_ref = _parse_sample_ref(el)
    return Clip(
        name=name, clip_type="audio",
        color_index=color_index, start_time=start_time,
        duration=duration, is_warped=is_warped,
        warp_mode=warp_mode, loop_on=loop_on, sample_ref=sample_ref,
    )


def _parse_midi_clip(el):
    name = _gv(el, "Name", "Value", "")
    color_str = _gv(el, "ColorIndex", "Value", "0")
    try:
        color_index = int(color_str)
    except ValueError:
        color_index = 0
    time_str = el.get("Time", "0")
    try:
        start_time = float(time_str)
    except ValueError:
        start_time = 0.0
    loop = el.find("Loop")
    duration = 0.0
    loop_on = False
    if loop is not None:
        end_str = _gv(loop, "LoopEnd", "Value", "0")
        try:
            duration = float(end_str)
        except ValueError:
            pass
        loop_on = _gv(loop, "LoopOn", "Value", "false") == "true"
    notes = []
    notes_el = el.find("Notes")
    if notes_el is not None:
        for key_track in notes_el.findall("KeyTracks"):
            key_el = key_track.find("MidiKey")
            if key_el is None:
                continue
            try:
                midi_key = int(key_el.get("Value", "0"))
            except ValueError:
                continue
            for note_el in key_track.findall("Notes/MidiNoteEvent"):
                try:
                    t = float(note_el.get("Time", "0"))
                    d = float(note_el.get("Duration", "0"))
                    v = int(note_el.get("Velocity", "100"))
                except ValueError:
                    continue
                notes.append({"pitch": midi_key, "time": t, "duration": d, "velocity": v})
    return Clip(
        name=name, clip_type="midi",
        color_index=color_index, start_time=start_time,
        duration=duration, loop_on=loop_on, notes=notes,
    )


def _parse_mixer(track_el, track):
    mixer = track_el.find("DeviceChain/Mixer")
    if mixer is None:
        return
    vol_el = mixer.find("Volume/Manual")
    if vol_el is None:
        return
    raw = vol_el.get("Value")
    if raw is None:
        return
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return
    if not math.isfinite(v):
        return
    track.volume = v


def _parse_sample_ref(el):
    sample_ref = el.find("SampleRef")
    if sample_ref is None:
        return None
    file_ref = sample_ref.find("FileRef")
    if file_ref is None:
        return None
    name = _gv(file_ref, "Name", "Value", "")
    path = _gv(file_ref, "Path", "Value", "")
    # Derive name from path if Name element is missing
    if not name and path:
        name = Path(path).stem

    rpt_str = _gv(file_ref, "RelativePathType", "Value", "0")
    try:
        rpt = int(rpt_str)
    except ValueError:
        rpt = 0

    # RelativePath format varies across Live versions:
    #  - Live 10/11: <RelativePath><RelativePathElement Dir="..." />...</RelativePath>
    #  - Live 12:    <RelativePath Value="Samples/Imported/file.wav" />
    rel_path = ""
    rel_path_el = file_ref.find("RelativePath")
    if rel_path_el is not None:
        dirs = []
        for el2 in rel_path_el.findall("RelativePathElement"):
            d = el2.get("Dir", "")
            if d:
                dirs.append(d)
        if dirs:
            rel_path = "/".join(dirs)
        else:
            rel_path = rel_path_el.get("Value", "")
    size_str = _gv(file_ref, "OriginalFileSize", "Value", "0")
    try:
        size = int(size_str)
    except ValueError:
        size = 0
    crc_str = _gv(file_ref, "OriginalCrc", "Value", "0")
    try:
        crc = int(crc_str)
    except ValueError:
        crc = 0
    pack_name = _gv(file_ref, "LivePackName", "Value", "")
    return SampleRef(
        name=name, path=path, relative_path=rel_path,
        relative_path_type=rpt, original_file_size=size,
        original_crc=crc, live_pack_name=pack_name,
    )
