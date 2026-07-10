# SPDX-License-Identifier: GPL-3.0-only
"""Generate synthetic parser-test .als fixtures with Live 12.4.2 XML structure.

ALL FIXTURES ARE SYNTHETIC PARSER FIXTURES — NOT ABLETON-AUTHORED SETS.

These fixtures approximate Ableton Live Set XML structure for ALScan parser
and analysis testing. They are NOT intended to open in Ableton Live.

WARNING: Do not attempt to open these fixtures in Ableton Live. A 2026-07
experiment attempting to generate Live-compatible Sets caused a fatal crash
in Ableton Live 12.4.2. This code exists for parser testing only.

Usage: python -m tests.fixtures.generate_parser_fixtures
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tests.fixtures.id_allocator import IdAllocator
from tests.fixtures.pointee_allocator import PointeeAllocator

OUTPUT_DIR = Path("local-validation")

_TRACK_ATTRS = 'SelectedToolPanel="7" SelectedTransformationName="" SelectedGeneratorName=""'


def _new_allocator() -> IdAllocator:
    a = IdAllocator()
    a.reserve({-1})
    return a


def midi_clip(alloc: IdAllocator, clip_name: str = "", duration: float = 4.0) -> str:
    slot_id = alloc.allocate("clip_slots")
    clip_id = alloc.allocate("clips")
    return f"""          <ClipSlot Id="{slot_id}">
            <LomId Value="0"/>
            <ClipSlot>
              <Value>
                <MidiClip Id="{clip_id}" Time="0">
                  <LomId Value="0"/>
                  <LomIdView Value="0"/>
                  <Name Value="{clip_name}"/>
                  <Color Value="2"/>
                  <Loop>
                    <LoopStart Value="0"/>
                    <LoopEnd Value="{duration}"/>
                    <StartRelative Value="0"/>
                    <LoopOn Value="true"/>
                    <OutMarker Value="{duration}"/>
                    <HiddenLoopStart Value="0"/>
                    <HiddenLoopEnd Value="{duration}"/>
                  </Loop>
                  <Notes>
                    <KeyTracks/>
                  </Notes>
                </MidiClip>
              </Value>
            </ClipSlot>
            <HasStop Value="true"/>
          </ClipSlot>"""


def audio_track(alloc: IdAllocator, pointee: PointeeAllocator, name: str, clips: str = "", devices: str = "") -> str:
    tid = alloc.allocate("tracks")
    pid = pointee.allocate(f"track:{name or 'unnamed'}")
    name_el = f'    <Name><EffectiveName Value="{name}"/><UserName Value="{name}"/><Annotation Value=""/></Name>'
    dev_chain = f"""    <DeviceChain>
      <Devices>
{devices}      </Devices>
      <MainSequencer>
        <ClipSlotList>
{clips}        </ClipSlotList>
      </MainSequencer>
    </DeviceChain>"""
    return f"""    <AudioTrack Id="{tid}" {_TRACK_ATTRS}>
    <LomId Value="0"/>
    <LomIdView Value="0"/>
{name_el}
    <Color Value="1"/>
    {dev_chain}
    <Mixer>
      <LomId Value="0"/>
      <ModulationSourceCount Value="0"/>
      <ParametersListWrapper LomId="0"/>
      {pointee.pointee_element(pid)}
    </Mixer>
  </AudioTrack>"""


def midi_track(alloc: IdAllocator, pointee: PointeeAllocator, name: str, clips: str = "", devices: str = "") -> str:
    tid = alloc.allocate("tracks")
    pid = pointee.allocate(f"track:{name or 'unnamed'}")
    name_el = f'    <Name><EffectiveName Value="{name}"/><UserName Value="{name}"/><Annotation Value=""/></Name>'
    dev_chain = f"""    <DeviceChain>
      <Devices>
{devices}      </Devices>
      <MainSequencer>
        <ClipSlotList>
{clips}        </ClipSlotList>
      </MainSequencer>
    </DeviceChain>"""
    return f"""    <MidiTrack Id="{tid}" {_TRACK_ATTRS}>
    <LomId Value="0"/>
    <LomIdView Value="0"/>
{name_el}
    <Color Value="2"/>
    {dev_chain}
    <Mixer>
      <LomId Value="0"/>
      <ModulationSourceCount Value="0"/>
      <ParametersListWrapper LomId="0"/>
      {pointee.pointee_element(pid)}
    </Mixer>
  </MidiTrack>"""


def builtin_device(tag: str) -> str:
    return f"""        <{tag}>
          <LomId Value="0"/>
          <PresetRef>
            <Value Value="Default"/>
          </PresetRef>
        </{tag}>"""


def make_als_xml(tracks: list[str], allocator: IdAllocator, pointee: PointeeAllocator, tempo: float = 120.0) -> str:
    errors = allocator.validate()
    if errors:
        raise ValueError(f"ID allocation errors: {errors}")
    perrors = pointee.validate()
    if perrors:
        raise ValueError(f"Pointee allocation errors: {perrors}")

    # Also allocate pointees for fixed objects
    maintrack_pid = pointee.allocate("MainTrack")
    prehear_pid = pointee.allocate("PreHearTrack")
    groove_pid = pointee.allocate("GroovePool")
    pointee.allocate("LiveSet")

    next_id = pointee.next_pointee_id()

    track_xmls = "\n".join(tracks)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12.0_12402" SchemaChangeCount="2" Creator="Ableton Live 12.4.2" Revision="0000000000000000000000000000000000000000">
  <LiveSet>
    <NextPointeeId Value="{next_id}"/>
    <OverwriteProtectionNumber Value="3076"/>
    <LomId Value="0"/>
    <LomIdView Value="0"/>
    <Tracks>
{track_xmls}
    </Tracks>
    <MainTrack SelectedToolPanel="7" SelectedTransformationName="" SelectedGeneratorName="">
      <LomId Value="0"/>
      <LomIdView Value="0"/>
      <TrackDelay>
        <Value Value="0"/>
        <IsValueSampleBased Value="false"/>
      </TrackDelay>
      <Name>
        <EffectiveName Value=""/>
        <UserName Value=""/>
        <Annotation Value=""/>
      </Name>
      <Color Value="6"/>
      <DeviceChain>
        <Devices/>
        <MainSequencer>
          <ClipSlotList/>
        </MainSequencer>
      </DeviceChain>
      <Mixer>
        <LomId Value="0"/>
        <ModulationSourceCount Value="0"/>
        <ParametersListWrapper LomId="0"/>
        {pointee.pointee_element(maintrack_pid)}
      </Mixer>
    </MainTrack>
    <PreHearTrack>
      <LomId Value="0"/>
      <Mixer>
        <LomId Value="0"/>
        <ModulationSourceCount Value="0"/>
        <ParametersListWrapper LomId="0"/>
        {pointee.pointee_element(prehear_pid)}
      </Mixer>
    </PreHearTrack>
    <SendsPre>
      <SendPreBool Id="0" Value="false"/>
      <SendPreBool Id="1" Value="false"/>
    </SendsPre>
    <Scenes>
      <Scene Id="0">
        <LomId Value="0"/>
        <FollowAction>
          <FollowTime Value="4"/>
          <IsLinked Value="true"/>
          <LoopIterations Value="1"/>
          <FollowActionA Value="4"/>
          <FollowActionB Value="0"/>
          <FollowChanceA Value="100"/>
          <FollowChanceB Value="0"/>
          <JumpIndexA Value="0"/>
          <JumpIndexB Value="0"/>
          <FollowActionEnabled Value="true"/>
        </FollowAction>
      </Scene>
    </Scenes>
    <Transport>
      <PhaseNudgeTempo Value="10"/>
      <LoopOn Value="false"/>
      <LoopStart Value="0"/>
      <LoopLength Value="4"/>
      <LoopIsSongStart Value="false"/>
      <CurrentTime Value="0"/>
      <PunchIn Value="false"/>
      <PunchOut Value="false"/>
      <MetronomeTickDuration Value="0"/>
      <DrawMode Value="false"/>
    </Transport>
    <SessionScrollPos X="0" Y="0"/>
    <SelectedBreakpointValue Value="0"/>
    <SignalModulations/>
    <GlobalQuantisation Value="4"/>
    <AutoQuantisation Value="0"/>
    <Grid>
      <FixedNumerator Value="1"/>
      <FixedDenominator Value="16"/>
      <GridIntervalPixel Value="20"/>
      <Ntoles Value="2"/>
      <SnapToGrid Value="true"/>
      <Fixed Value="false"/>
    </Grid>
    <ScaleInformation>
      <Root Value="0"/>
      <Name Value="0"/>
    </ScaleInformation>
    <InKey Value="true"/>
    <SmpteFormat Value="0"/>
    <TimeSelection>
      <AnchorTime Value="0"/>
      <OtherTime Value="0"/>
    </TimeSelection>
    <SequencerNavigator>
      <BeatTimeHelper>
        <CurrentZoom Value="0.254945054945055"/>
      </BeatTimeHelper>
      <ScrollerPos X="0" Y="0"/>
      <ClientSize X="1351" Y="725"/>
    </SequencerNavigator>
    <IsContentSplitterOpen Value="true"/>
    <IsExpressionSplitterOpen Value="true"/>
    <ExpressionLanes>
      <MidiEditorLaneModel Id="0">
        <Type Value="5"/>
        <Size Value="41"/>
        <IsMinimized Value="true"/>
      </MidiEditorLaneModel>
      <MidiEditorLaneModel Id="1">
        <Type Value="0"/>
        <Size Value="41"/>
        <IsMinimized Value="true"/>
      </MidiEditorLaneModel>
    </ExpressionLanes>
    <ContentLanes>
      <MidiEditorLaneModel Id="0">
        <Type Value="2"/>
        <Size Value="41"/>
        <IsMinimized Value="false"/>
      </MidiEditorLaneModel>
    </ContentLanes>
    <ViewStateFxSlotCount Value="4"/>
    <ViewStateSessionMixerVolumeSectionHeight Value="120"/>
    <ViewStateArrangerMixerVolumeSectionHeight Value="120"/>
    <ShouldSceneTempoAndTimeSignatureBeVisible Value="false"/>
    <WaveformVerticalZoomFactor Value="1"/>
    <IsWaveformVerticalZoomActive Value="true"/>
    <Tempo>
      <Manual Value="{tempo}"/>
    </Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/>
          <Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators>
      <Locators/>
    </Locators>
    <DetailClipKeyMidis/>
    <TracksListWrapper LomId="0"/>
    <VisibleTracksListWrapper LomId="0"/>
    <ReturnTracksListWrapper LomId="0"/>
    <ScenesListWrapper LomId="0"/>
    <CuePointsListWrapper LomId="0"/>
    <SelectedDocumentViewInMainWindow Value="1"/>
    <Annotation Value=""/>
    <SoloOrPflSavedValue Value="true"/>
    <SoloInPlace Value="true"/>
    <CrossfadeCurve Value="2"/>
    <LatencyCompensation Value="2"/>
    <HighlightedTrackIndex Value="0"/>
    <GroovePool>
      <LomId Value="0"/>
      <Grooves/>
    </GroovePool>
    <AutomationMode Value="false"/>
    <SnapAutomationToGrid Value="true"/>
    <ArrangementOverdub Value="false"/>
    <ColorSequenceIndex Value="0"/>
    <AutoColorPickerForPlayerAndGroupTracks>
      <NextColorIndex Value="10"/>
    </AutoColorPickerForPlayerAndGroupTracks>
    <AutoColorPickerForReturnAndMainTracks>
      <NextColorIndex Value="4"/>
    </AutoColorPickerForReturnAndMainTracks>
    <ViewData Value="{{}}"/>
    <ResetNonautomatedMidiControllersOnClipStarts Value="true"/>
    <MidiFoldIn Value="false"/>
    <MidiFoldMode Value="0"/>
    <MultiClipFocusMode Value="false"/>
    <MultiClipLoopBarHeight Value="0"/>
    <MidiPrelisten Value="false"/>
    <LinkedTrackGroups/>
    <NoteSpellingPreference Value="0"/>
    <AccidentalSpellingPreference Value="3"/>
    <PreferFlatRootNote Value="false"/>
    <UseWarperLegacyHiQMode Value="false"/>
    <VideoWindowRect Top="-2147483648" Left="-2147483648" Bottom="-2147483648" Right="-2147483648"/>
    <ShowVideoWindow Value="true"/>
    <TuningSystems/>
    <TrackHeaderWidth Value="93"/>
    <ViewStateMainWindowClipDetailOpen Value="false"/>
    <ViewStateMainWindowHiddenOtherDocViewTypeClipDetailOpen Value="false"/>
    <ViewStateMainWindowHiddenOtherDocViewTypeDeviceDetailOpen Value="true"/>
    <ViewStateMainWindowDeviceDetailOpen Value="true"/>
    <ViewStateSecondWindowClipDetailOpen Value="true"/>
    <ViewStateSecondWindowDeviceDetailOpen Value="false"/>
    <ViewStates>
      <MixerInArrangement Value="0"/>
      <ArrangerMixerIO Value="1"/>
      <ArrangerMixerSends Value="1"/>
      <ArrangerMixerReturns Value="1"/>
      <ArrangerMixerVolume Value="1"/>
      <ArrangerMixerTrackOptions Value="1"/>
      <ArrangerMixerCrossFade Value="1"/>
      <ArrangerMixerTrackPerformanceImpactMeter Value="1"/>
      <MixerInSession Value="0"/>
      <SessionIO Value="1"/>
      <SessionSends Value="1"/>
      <SessionReturns Value="1"/>
      <SessionVolume Value="1"/>
      <SessionTrackOptions Value="1"/>
      <SessionCrossFade Value="1"/>
      <SessionTrackPerformanceImpactMeter Value="1"/>
      <SessionShowOverView Value="1"/>
      <ArrangerIO Value="1"/>
      <ArrangerReturns Value="0"/>
      <ArrangerVolume Value="1"/>
      <ArrangerTrackOptions Value="0"/>
      <ArrangerShowOverView Value="0"/>
    </ViewStates>
    <NoteAlgorithms/>
  </LiveSet>
</Ableton>"""


def write_als(path: Path, xml: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = xml.encode("utf-8")
    gz = gzip.compress(raw)
    path.write_bytes(gz)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"  {path.name}  SHA-256: {sha}")
    return path


# ── Parser-test fixture generation ───────────────────────────────────


def generate():
    """Generate synthetic parser-test fixtures. NOT for Ableton Live testing."""


if __name__ == "__main__":
    print("This module generates synthetic parser-test fixtures only.")
    print("These fixtures are NOT intended to open in Ableton Live.")
    generate()
