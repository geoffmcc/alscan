"""Generate .als test fixtures for all 19 alscan checks.

Usage: python -m tests.fixtures.generate
"""

from __future__ import annotations

import gzip
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def make_als_xml(
    tracks: list[str],
    creator: str = "Ableton Live 12.4.2",
    major: str = "12",
    minor: str = "4",
    tempo: float = 120.0,
    ts_num: int = 4,
    ts_den: int = 4,
    has_locators: bool = True,
) -> str:
    """Build a complete .als XML string from track XML strings."""
    track_xmls = "\n".join(tracks)
    locators_xml = "    <Locators>\n      <Locators/>\n    </Locators>" if has_locators else "    <Locators><Locators/></Locators>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Ableton Creator="{creator}" MajorVersion="{major}" MinorVersion="{minor}">
  <LiveSet>
    <Tempo>
      <Manual Value="{tempo}"/>
    </Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="{ts_num}"/>
          <Denominator Value="{ts_den}"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    {locators_xml}
    <Tracks>
{track_xmls}
    </Tracks>
  </LiveSet>
</Ableton>"""


def write_als(filename: str, xml: str) -> Path:
    path = FIXTURES_DIR / filename
    raw = xml.encode("utf-8")
    gz = gzip.compress(raw)
    path.write_bytes(gz)
    return path


# ---------------------------------------------------------------------------
# Helper track builders
# ---------------------------------------------------------------------------

def audio_track(track_id: int, name: str = "", freeze: bool = False,
                clips: str = "", devices: str = "",
                color: int = 1, group_id: int = -1) -> str:
    freeze_el = '    <Freeze Value="true"/>\n' if freeze else ""
    group_el = f'    <TrackGroupId Value="{group_id}"/>\n' if group_id >= 0 else ""
    name_el = f'    <Name><EffectiveName Value="{name}"/></Name>\n' if name else '    <Name><EffectiveName Value=""/></Name>\n'
    return f"""    <AudioTrack Id="{track_id}">
{name_el}    <ColorIndex Value="{color}"/>
{freeze_el}{group_el}    <DeviceChain>
      <Devices>
{devices}      </Devices>
      <MainSequencer>
        <ClipSlotList>
{clips}        </ClipSlotList>
      </MainSequencer>
    </DeviceChain>
  </AudioTrack>"""


def midi_track(track_id: int, name: str = "", freeze: bool = False,
               clips: str = "", devices: str = "",
               color: int = 2, group_id: int = -1) -> str:
    freeze_el = '    <Freeze Value="true"/>\n' if freeze else ""
    group_el = f'    <TrackGroupId Value="{group_id}"/>\n' if group_id >= 0 else ""
    name_el = f'    <Name><EffectiveName Value="{name}"/></Name>\n' if name else '    <Name><EffectiveName Value=""/></Name>\n'
    return f"""    <MidiTrack Id="{track_id}">
{name_el}    <ColorIndex Value="{color}"/>
{freeze_el}{group_el}    <DeviceChain>
      <Devices>
{devices}      </Devices>
      <MainSequencer>
        <ClipSlotList>
{clips}        </ClipSlotList>
      </MainSequencer>
    </DeviceChain>
  </MidiTrack>"""


def group_track(track_id: int, name: str = "", color: int = 3) -> str:
    name_el = f'    <Name><EffectiveName Value="{name}"/></Name>\n' if name else '    <Name><EffectiveName Value=""/></Name>\n'
    return f"""    <GroupTrack Id="{track_id}">
{name_el}    <ColorIndex Value="{color}"/>
    <DeviceChain>
      <Devices/>
      <MainSequencer>
        <ClipSlotList/>
      </MainSequencer>
    </DeviceChain>
  </GroupTrack>"""


def master_track(devices: str = "") -> str:
    return f"""    <MasterTrack Id="-1">
    <Name><EffectiveName Value="Master"/></Name>
    <ColorIndex Value="5"/>
    <DeviceChain>
      <Devices>
{devices}      </Devices>
      <MainSequencer>
        <ClipSlotList/>
      </MainSequencer>
    </DeviceChain>
  </MasterTrack>"""


def return_track(track_id: int, name: str = "", clips: str = "", color: int = 4) -> str:
    name_el = f'    <Name><EffectiveName Value="{name}"/></Name>\n' if name else '    <Name><EffectiveName Value=""/></Name>\n'
    return f"""    <ReturnTrack Id="{track_id}">
{name_el}    <ColorIndex Value="{color}"/>
    <DeviceChain>
      <Devices/>
      <MainSequencer>
        <ClipSlotList>
{clips}        </ClipSlotList>
      </MainSequencer>
    </DeviceChain>
  </ReturnTrack>"""


# ---------------------------------------------------------------------------
# Clip builders
# ---------------------------------------------------------------------------

def audio_clip(clip_name: str = "", sample_path: str = "",
               sample_name: str = "", relative_path: str = "",
               rpt: int = 1, size: int = 12345, crc: int = 67890,
               pack_name: str = "", duration: float = 8.0,
               warped: bool = False) -> str:
    sample_block = ""
    warp_el = '      <IsWarped Value="true"/>\n' if warped else ""
    if sample_path:
        name_block = f'        <Name Value="{sample_name}"/>\n' if sample_name else ""
        pack_block = f'        <LivePackName Value="{pack_name}"/>\n' if pack_name else ""
        rp_block = f'        <RelativePath><RelativePathElement Dir="{relative_path}"/></RelativePath>\n' if relative_path else ''
        sample_block = f"""      <SampleRef>
        <FileRef>
{name_block}        <Path Value="{sample_path}"/>
        <RelativePathType Value="{rpt}"/>
{rp_block}        <Type Value="1"/>
        <OriginalFileSize Value="{size}"/>
        <OriginalCrc Value="{crc}"/>
        <SourceHint Value=""/>
{pack_block}        </FileRef>
      </SampleRef>"""
    return f"""          <ClipSlot>
            <ClipSlot>
              <HasStop Value="true"/>
              <Value>
                <AudioClip Time="0.0">
                  <Name Value="{clip_name}"/>
                  <ColorIndex Value="1"/>
{warp_el}{sample_block}                  <Loop>
                    <LoopEnd Value="{duration}"/>
                    <LoopOn Value="false"/>
                  </Loop>
                </AudioClip>
              </Value>
            </ClipSlot>
          </ClipSlot>"""


def midi_clip(clip_name: str = "", duration: float = 4.0) -> str:
    return f"""          <ClipSlot>
            <ClipSlot>
              <HasStop Value="true"/>
              <Value>
                <MidiClip Time="0.0">
                  <Name Value="{clip_name}"/>
                  <ColorIndex Value="2"/>
                  <Loop>
                    <LoopEnd Value="{duration}"/>
                    <LoopOn Value="true"/>
                  </Loop>
                  <Notes>
                    <KeyTracks>
                      <MidiKey Value="60"/>
                      <Notes>
                        <MidiNoteEvent Time="0" Duration="0.5" Velocity="100"/>
                      </Notes>
                    </KeyTracks>
                  </Notes>
                </MidiClip>
              </Value>
            </ClipSlot>
          </ClipSlot>"""


# ---------------------------------------------------------------------------
# Device builders
# ---------------------------------------------------------------------------

def builtin_device(tag: str, preset: str = "Default") -> str:
    return f"""        <{tag}>
          <PresetRef>
            <Value Value="{preset}"/>
          </PresetRef>
        </{tag}>"""


def plugin_device_vst(plugin_name: str, path: str, uid: str = "12345") -> str:
    return f"""        <PluginDevice>
          <PluginDesc>
            <VstPluginInfo>
              <Name Value="{plugin_name}"/>
              <Path Value="{path}"/>
              <UniqueId Value="{uid}"/>
            </VstPluginInfo>
          </PluginDesc>
        </PluginDevice>"""


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------

GOOD_SAMPLE = "C:/Audio/Project Samples/kick.wav"
GOOD_SAMPLE_NAME = "kick"
BROKEN_SAMPLE = "Z:/nonexistent/sample.wav"
BROKEN_SAMPLE_NAME = "Broken Sample"
PACK_SAMPLE_PATH = "C:/ProgramData/Ableton/Packs/Factory/amen.wav"
DUPLICATE_SAMPLE_PATH = "D:/shared/loop.wav"
BROKEN_PLUGIN_PATH = "Z:/VST/Nonexistent.dll"


def generate_clean_project():
    """Minimal project with no issues. MIDI clips only — no sample refs to go missing."""
    tracks = [
        midi_track(0, "Synth", clips=midi_clip("Chord")),
        midi_track(1, "Keys", clips=midi_clip("Arp")),
    ]
    xml = make_als_xml(tracks)
    return write_als("clean.als", xml)


def generate_all_checks_project():
    """Comprehensive project exercising all 15 checks."""

    clips_missing = audio_clip("Missing Clip", BROKEN_SAMPLE, BROKEN_SAMPLE_NAME, "nonexistent/sample.wav", 1)
    clips_shared = audio_clip("Loop Clip", DUPLICATE_SAMPLE_PATH, "loop", "shared/loop.wav", 1)
    clips_pack = audio_clip("Pack Clip", PACK_SAMPLE_PATH, "Pack Sample", "", 2, pack_name="Factory Pack")
    clips_warped = audio_clip("Warped Loop", GOOD_SAMPLE, GOOD_SAMPLE_NAME, "Samples/kick.wav", 1, warped=True)
    clips_midi = midi_clip("MIDI 1", 4.0)

    # 21 clips to trigger unfrozen_heavy_tracks (21 > 20)
    heavy_clips = "\n".join(audio_clip(f"Clip {i}", GOOD_SAMPLE, GOOD_SAMPLE_NAME, "Samples/kick.wav", 1) for i in range(21))

    heavy_devices = "\n".join([
        plugin_device_vst("Serum", "C:/VST/Serum.dll", "11111"),
        plugin_device_vst("Ozone", "C:/VST/Ozone.dll", "22222"),
        plugin_device_vst("Kontakt", "C:/VST/Kontakt.dll", "33333"),
        builtin_device("Compressor2"),
        builtin_device("Eq8"),
    ])

    frozen_vst = plugin_device_vst("Massive", BROKEN_PLUGIN_PATH, "44444")

    # 10 builtin devices to trigger high_device_count (> 8)
    device_hell = "\n".join(builtin_device(d) for d in [
        "Compressor2", "Eq8", "Reverb", "Delay", "AutoFilter",
        "GlueCompressor", "Gate", "Phaser", "Chorus", "Flanger",
    ])

    tracks = [
        # [0] Empty track (empty_tracks)
        audio_track(0, "Empty Track"),

        # [1] Unnamed track (unnamed_tracks)
        audio_track(1, ""),

        # [2] Audio 1 — missing sample (missing_samples) + shared sample (duplicate_samples with [3])
        audio_track(2, "Audio 1", clips=clips_missing + clips_shared),

        # [3] Audio 1 — duplicate name (duplicate_track_names) + shared sample (duplicate_samples with [2])
        audio_track(3, "Audio 1", clips=clips_shared),

        # [4] Heavy Track — 21 clips + 5 devices incl Serum+Ozone (unfrozen_heavy_tracks, cpu_heavy, latency)
        audio_track(4, "Heavy Track", clips=heavy_clips, devices=heavy_devices),

        # [5] Frozen Synth — frozen + broken VST (frozen_plugins, frozen_tracks)
        midi_track(5, "Frozen Synth", freeze=True, clips=midi_clip("Frozen MIDI"), devices=frozen_vst),

        # [6] Device Hell — 10 devices (high_device_count)
        midi_track(6, "Device Hell", devices=device_hell),

        # [7] Empty Group (empty_groups)
        group_track(7, "Empty Group"),

        # [8] Populated Group — has children, no issue
        group_track(8, "Populated Group"),

        # [9] Group Child — group_id=8, no issue
        audio_track(9, "Group Child", clips=midi_clip("Child Clip"), group_id=8),

        # [10] Unused Reverb — return track with no clips (unused_returns)
        return_track(10, "Unused Reverb"),

        # [11] Used Delay — return track WITH clips → considered "used"
        return_track(11, "Used Delay", clips=midi_clip("Delay Return")),

        # [12] Pack Sample Track — pack sample not found (missing_pack_samples)
        audio_track(12, "Pack Track", clips=clips_pack),

        # [13] Warped Track — warped audio clip (warped_clips)
        audio_track(13, "Warped Track", clips=clips_warped),
    ]

    master = master_track(devices=builtin_device("Limiter"))

    xml = make_als_xml(tracks + [master], tempo=250.0, has_locators=False)
    return write_als("all_checks.als", xml)


def generate_frozen_returns_project():
    """Project where return tracks have clips — should NOT trigger unused_returns."""
    tracks = [
        midi_track(0, "Synth", clips=midi_clip("Chord")),
        return_track(1, "Reverb", clips=midi_clip("Verb Clip")),
    ]
    xml = make_als_xml(tracks)
    return write_als("frozen_returns.als", xml)


def generate():
    clean = generate_clean_project()
    print(f"  {clean.name} — clean project (0 findings)")

    all_chk = generate_all_checks_project()
    print(f"  {all_chk.name} — exercises all 19 checks")

    frozen = generate_frozen_returns_project()
    print(f"  {frozen.name} — return with clips (no unused_returns)")


if __name__ == "__main__":
    generate()
