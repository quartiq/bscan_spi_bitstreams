# bscan_spi_bitstreams

JTAG-SPI proxy bitstreams to be used with the [OpenOCD](http://openocd.org/)
[jtagspi](https://github.com/ntfreak/openocd/blob/master/src/flash/nor/jtagspi.c)
flash driver -- but potentially other JTAG software as well. These bitstreams have
been tested on the
[KC705](https://github.com/ntfreak/openocd/blob/master/tcl/board/kc705.cfg),
[Pipistrello](https://github.com/ntfreak/openocd/blob/master/tcl/board/pipistrello.cfg),
and other boards.

All bitstreams are generated with [xilinx_bscan_spi.py](xilinx_bscan_spi.py)
as contained in this repository.
