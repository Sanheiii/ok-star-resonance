# Protobuf files required by packet capture

Compile the game protocol with Python's protobuf generator and place the output
in this directory as one of:

- `blueprotobuf_pb2.py`
- `blueprotobuf_package_pb2.py`
- `BlueProtobuf_pb2.py`

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
changes are required after adding it. `Position` must contain `x`, `y`, and `z`;
attributes must contain `id` and `raw_data`.
