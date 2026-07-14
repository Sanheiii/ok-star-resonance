# Protobuf files required by packet capture

`BlueProtobuf_pb2.py` is generated from the wire-compatible subset in
`BlueProtobuf.proto`, extracted from StarResonanceMITMServer's zproto
schemas. It provides `WorldNtf.SyncContainerData.vData.sceneData.pos` and the
minimal `WorldNtf.EnterScene` subset reconstructed from resonance-logs-cn's
prost-generated Rust declarations.

The missing AOI delta definitions verified against resonance-logs-cn have been
added to the repository subset, so this generated module now handles both full
container sync and incremental movement. No legacy pb2 module is required.

Regenerate the repository module from the workspace root with:

```powershell
.\.venv\Scripts\python.exe -m grpc_tools.protoc `
  --proto_path=src\packet_capture\proto `
  --python_out=src\packet_capture\proto `
  src\packet_capture\proto\BlueProtobuf.proto
```

The generated module supplies these incremental messages:

- `SyncContainerData`
- `EnterScene`
- `EnterSceneInfo`
- `Entity`
- `SyncToMeDeltaInfo`
- `SyncNearDeltaInfo`
- `AoiSyncDelta`
- `AttrCollection`
- `Attr`
- `Position`

All fields use the source repository's lowerCamelCase style and the notify
wrappers are nested under `WorldNtf`.
