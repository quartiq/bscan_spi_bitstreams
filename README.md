# bscan_spi_bitstreams

JTAG-SPI proxy bitstreams to be used with the [OpenOCD](http://openocd.org/) [jtagspi](https://github.com/ntfreak/openocd/blob/master/src/flash/nor/jtagspi.c) flash driver -- but potentially other JTAG software as well. These bitstreams have been tested on the [KC705](https://github.com/ntfreak/openocd/blob/master/tcl/board/kc705.cfg), [Pipistrello](https://github.com/ntfreak/openocd/blob/master/tcl/board/pipistrello.cfg), Kasli, Sayma-AMC+Sayma-RTM, Lattice ECP5 Versa and several other boards.

Currently, bitstreams for Xilinx and Lattice chips are generated with the following scripts:

* [xilinx_bscan_spi.py](xilinx_bscan_spi.py): [**(o)Migen**](https://github.com/m-labs/migen/) script that generates bitstreams for Xilinx chips; all the generated `.bit` bistreams are contained in this repository.
* [lattice_bscan_spi.py](lattice_bscan_spi.py): [**nMigen**](https://github.com/m-labs/nmigen/) script that generates bitstreams for Lattice chips; a `.svf` JTAG programming vector generated for LFE5UM-45F is currently contained in this repository.
  * _Note on usage: After programming the device through JTAG, the `reset halt` command is required before performing flash commands on OpenOCD. Also note that when using jtagspi, the private instruction `0x32` must be shifted into the JTAG IR on Lattice FPGAs (see item "ER1, ER2" on p.758 of the [FPGA Libraries Reference Guide 3.11](http://www.latticesemi.com/view_document?document_id=52656) for details)._

## Versions

**Note**: The bitstreams in this branch require openocd as of [867bdb2](https://github.com/ntfreak/openocd/tree/867bdb2e9248a974f7db0a99fbe5d2dd8b46d25d) or later.
Since 2017-08-08 and as of 2019-06-11 there has not been an openocd release including this.

**Note**: Bitstreams for previous openocd releases are in the [single-tap](https://github.com/quartiq/bscan_spi_bitstreams/commits/single-tap)
branch.