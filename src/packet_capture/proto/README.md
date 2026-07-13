# Protobuf files required by packet capture

Compile the game protocol with Python's protobuf generator and place the output
in this directory as `BlueProtobuf_pb2.py`.

The generated module must expose these messages (including their referenced
child messages):

- `SyncContainerData`
- `SyncToMeDeltaInfo`
- `SyncNearDeltaInfo`
- `AoiSyncDelta`
- `AttrCollection`
- `Attr`
- `Position`

The parser reloads the module when capture packets arrive, so no other source
changes are required after adding it. The generated fields must retain their
PascalCase names: `Position.X/Y/Z`, `Attr.Id/RawData`, `AoiSyncDelta.Uuid/Attrs`,
`SyncToMeDeltaInfo.DeltaInfo`, and `SyncNearDeltaInfo.DeltaInfos`.
