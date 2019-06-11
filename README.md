# bscan_spi_bitstreams

JTAG-SPI proxy bitstreams to be used with the [OpenOCD](http://openocd.org/)
[jtagspi](https://github.com/ntfreak/openocd/blob/master/src/flash/nor/jtagspi.c)
flash driver -- but potentially other JTAG software as well. These bitstreams have
been tested on the
[KC705](https://github.com/ntfreak/openocd/blob/master/tcl/board/kc705.cfg),
[Pipistrello](https://github.com/ntfreak/openocd/blob/master/tcl/board/pipistrello.cfg),
Kasli, Sayma-AMC+Sayma-RTM, and several other boards.

All bitstreams are generated with [xilinx_bscan_spi.py](xilinx_bscan_spi.py)
as contained in this repository.

## Versions

**Note**: The bitstreams in this branch require openocd as of [867bdb2](https://github.com/ntfreak/openocd/tree/867bdb2e9248a974f7db0a99fbe5d2dd8b46d25d) or later.
Since 2017-08-08 and as of 2019-06-11 there has not been an openocd release including this.

**Note**: Bitstreams for previous openocd releases are in the [single-tap](https://github.com/quartiq/bscan_spi_bitstreams/commits/single-tap)
branch.
