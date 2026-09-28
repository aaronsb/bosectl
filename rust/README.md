# bose-bmap

Rust implementation of [bosectl](https://github.com/aaronsb/bosectl): control Bose headphones over the BMAP protocol on Bluetooth RFCOMM. Linux only; the transport uses BlueZ RFCOMM sockets.

The crate ships a library and the `bmapctl` command-line tool.

```bash
cargo install bose-bmap   # installs bmapctl
bmapctl status
```

As a library, the crate is named `bose-bmap` on crates.io and imported as `bmap`:

```toml
[dependencies]
bose-bmap = "0.4"
```

```rust
let mut conn = bmap::connect(None, None)?;
println!("{:?}", conn.status()?);
```

Supported devices, protocol notes, and the Python and C++ implementations live in the [main repository](https://github.com/aaronsb/bosectl).

MIT licensed.
