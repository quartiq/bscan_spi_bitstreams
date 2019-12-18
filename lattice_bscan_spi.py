#!/usr/bin/python3

from nmigen import *
from nmigen.lib.cdc import FFSynchronizer
from nmigen.lib.io import Pin
from nmigen.build import *
from nmigen.vendor.lattice_ecp5 import *


"""This nMigen script produces proxy bitstream to allow programming SPI flashes
behind FPGAs. It was created based on ./xilinx_bscan_spi.py.

Currently, bitstream binaries have been built with this script on the following
platforms:
* Lattice ECP5

https://github.com/m-labs/nmigen
"""


def _wire_layout():
    return [
        ("sel"     , 1),
        ("shift"   , 1),
        ("capture" , 1),
        ("tck"     , 1),
        ("tdi"     , 1),
        ("tdo"     , 1),
    ]


class JTAGtoSPI(Elaboratable):
    def __init__(self, *, bits=32, spi_pins=None, **kwargs):
        self._bits = bits

        self._spi_pins = spi_pins
        self.jtag = Record(_wire_layout())

        self.cs_n = Pin(1, "oe")
        self.clk  = Pin(1, "oe")
        self.mosi = Pin(1, "oe")
        self.miso = Pin(1, "i")

        #
        self.cs_n.o.reset = 1
        self.mosi.o.reset_less = True

        self.jtag_sel1_capture = Signal()   # JTAG chain 1 is selected & in Capture-DR state?
        self.jtag_sel1_shift   = Signal()   # JTAG chain 1 is selected & in Shift-DR state?

        # For JTAGF/JTAGG
        if set(kwargs).intersection(["jtagf", "jtagg"]):
            if kwargs.get("jtagf"):
                self._jtagf = True
            elif kwargs.get("jtagg"):
                self._jtagg = True
            else:
                raise KeyError("Can't use JTAGF and JTAGG at the same time")


    def _detect_jtag_state(self, module):
        # JTAGF / JTAGG
        if True in [hasattr(self, t) for t in ["_jtagf", "_jtagg"]]:
            # Add a JTAGG module to expose internal JTAG signals to FPGA
            if hasattr(self, "_jtagf"):
                jtag_name = "JTAGF"
            elif hasattr(self, "_jtagg"):
                jtag_name = "JTAGG"
            jtag_sel1_capture_or_shift = Signal()
            jtag_rti1 = Signal()
            jtag_rst_n = Signal()
            module.submodules += Instance(jtag_name,
                                          i_JTDO1=self.jtag.tdo,
                                          o_JTDI=self.jtag.tdi,
                                          o_JTCK=self.jtag.tck,
                                          o_JRTI1=jtag_rti1,
                                          o_JRSTN=jtag_rst_n,
                                          o_JSHIFT=self.jtag.shift,
                                          o_JCE1=jtag_sel1_capture_or_shift)
            # Detect that when chain 1 is selected, whether or not TAP is in Capture-DR or Shift-DR state
            module.d.comb += [
                self.jtag_sel1_capture.eq(jtag_sel1_capture_or_shift & ~self.jtag.shift),
                self.jtag_sel1_shift.eq(jtag_sel1_capture_or_shift & self.jtag.shift)
            ]
            # Detect whether or not chain 1 is selected:
            # Selection happens right after the TRST pin is deasserted, 
            #   i.e. TAP just left Test-Logic-Reset state and is entering Run-Test/Idle state;
            # Thus, when TAP enters RTI state, if JRTI1 is high,
            #   it is implied chain 1 is selected until TAP enters TLR state again
            with module.FSM():
                with module.State("IDLE"):
                    with module.If(~jtag_rst_n):
                        module.d.sync += self.jtag.sel.eq(0)
                        module.next = "TLRST"
                with module.State("TLRST"):
                    with module.If(~self.jtag.sel):
                        module.d.sync += self.jtag.sel.eq(jtag_rti1)
                    with module.Else():
                        module.next = "IDLE"


    def elaborate(self, platform):
        m = Module()

        bits = Signal(self._bits, reset_less=True)
        head = Signal(range(len(bits)), reset=len(bits)-1)
        m.domains.sync = cd_sync = ClockDomain()

        if self._spi_pins is not None:
            m.submodules += [
                platform.get_tristate(self.cs_n, self._spi_pins.cs_n, None, False),
                platform.get_tristate(self.mosi, self._spi_pins.mosi, None, False),
                platform.get_input(self.miso, self._spi_pins.miso, None, False)
            ]
            m.d.comb += [
                self._spi_pins.wp.eq(1),
                self._spi_pins.hold.eq(1)
            ]
            self._detect_jtag_state(m)
        # For simulation purpose using no Pins:
        else:
            m.d.comb += [
                self.jtag_sel1_capture.eq(self.jtag.sel & self.jtag.capture),
                self.jtag_sel1_shift.eq(self.jtag.sel & self.jtag.shift)
            ]

        m.d.comb += [
            cd_sync.rst.eq(self.jtag_sel1_capture),
            cd_sync.clk.eq(self.jtag.tck),
            self.cs_n.oe.eq(self.jtag.sel),
            self.clk.oe.eq(self.jtag.sel),
            self.mosi.oe.eq(self.jtag.sel),
            self.jtag.tdo.eq(self.miso.i),
            # Positive edge: JTAG TAP outputs; SPI device gets input from FPGA
            # Negative edge: JTAG TAP gets input; SPI device outputs to FPGA
            self.clk.o.eq(~self.jtag.tck),
        ]

        # Latency calculation (in half cycles):
        # 0 (falling TCK, rising CLK):
        #   JTAG adapter: set TDI
        # 1 (rising TCK, falling CLK):
        #   JTAG2SPI: sample TDI -> set MOSI
        #   SPI: set MISO
        # 2 (falling TCK, rising CLK):
        #   SPI: sample MOSI
        #   JTAG2SPI (BSCAN primitive): sample MISO -> set TDO
        # 3 (rising TCK, falling CLK):
        #   JTAG adapter: sample TDO
        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.jtag_sel1_shift & self.jtag.tdi):
                    m.next = "HEAD"
            with m.State("HEAD"):
                m.d.sync += [
                    bits.eq(Cat(self.jtag.tdi, bits)),
                    head.eq(head - 1)
                ]
                with m.If(head == 0):
                    m.next = "XFER"
            with m.State("XFER"):
                m.d.sync += bits.eq(bits - 1)
                with m.If(bits == 0):
                    m.next = "IDLE"
        m.d.comb += [
            self.mosi.o.eq(self.jtag.tdi),
            self.cs_n.o.eq(~fsm.ongoing("XFER"))
        ]

        return m


class LatticeECP5(Elaboratable):
    toolchain="Trellis"

    def elaborate(self, platform):
        m = Module()

        io_spiflash = platform.request("spi_flash_1x", dir={'cs_n':'-',
                                                            'mosi':'-',
                                                            "miso":'-'})
        m.submodules.j2s = j2s = JTAGtoSPI(spi_pins=io_spiflash, jtagg=True)

        # Add a USRMCLK module to use a user clock as MCLK
        # "The ECP5 and ECP5-5G devices provide a solution for users 
        # to choose any user clock as MCLK under this scenario 
        # by instantiating USRMCLK macro in your Verilog or VHDL."
        # (see Section 6.1.2 of FPGA-TN-02039-1.7, 
        #  "ECP5 and ECP5-5G sysCONFIG Usage Guide Technical Note")
        m.submodules += Instance("USRMCLK",
                                 i_USRMCLKI=j2s.clk,
                                 i_USRMCLKTS=0)

        # For some reason, the clk100 must be requested and used to drive a domain in the design
        m.domains.clk100 = cd_clk100 = ClockDomain(reset_less=True)
        m.d.comb += cd_clk100.clk.eq(platform.request("clk100").i)

        return m


class LatticeECP5BscanSpi(LatticeECP5Platform):
    def make_spi():
        io = []
        io_1x = [
            Attrs(IO_STANDARD="LVCMOS33"),
            Subsignal("cs_n", Pins("R2", dir="o")),
            Subsignal("mosi", Pins("W2", dir="o", assert_width=1)),
            Subsignal("miso", Pins("V2", dir="i", assert_width=1)),
            Subsignal("wp",   Pins("Y2", dir="o", assert_width=1)),
            Subsignal("hold", Pins("W1", dir="o", assert_width=1))
        ]
        io.append(Resource.family(0, default_name="spi_flash", ios=io_1x,
                                  name_suffix="1x"))
        return io

    def make_clk():
        return (
            Resource("clk100", 0, DiffPairs("P3", "P4", dir="i"),
                     Clock(100e6), Attrs(IO_TYPE="LVDS"))
        )

    device     = "LFE5UM-45F"
    package    = "BG381"
    speed      = "8"
    resources  = [*make_spi(), make_clk()]
    connectors = []
    top_class  = LatticeECP5

    def __init__(self, toolchain="Trellis"):
        LatticeECP5Platform.__init__(self, toolchain=toolchain)


class LatticeBscanSpi:
    targets = {
        "LFE5UM-45F": LatticeECP5BscanSpi
    }

    def __new__(cls, target, *args, **kwargs):
        newcls = cls.targets[target]
        self = newcls.__new__(newcls, *args, **kwargs)
        newcls.__init__(self, *args, **kwargs)
        return self

    @classmethod
    def make(cls, target, errors=False):
        Top = cls.targets[target].top_class
        platform = cls(target, Top.toolchain)
        top = Top(platform)
        name = "bscan_spi_{}".format(target.lower().replace("-",""))
        try:
            platform.build(top, name=name)
        except Exception as e:
            print(("ERROR: lattice_bscan_spi build failed for {}: {}")
                  .format(target, e))
            if errors:
                raise


if __name__ == "__main__":
    import argparse
    import multiprocessing
    p = argparse.ArgumentParser(description="build bscan_spi bitstreams "
                                "for openocd jtagspi flash driver")
    p.add_argument("device", nargs="*",
                   default=sorted(list(LatticeBscanSpi.targets)),
                   help="build for these devices (default: %(default)s)")
    p.add_argument("-p", "--parallel", default=1, type=int,
                   help="number of parallel builds (default: %(default)s)")
    args = p.parse_args()
    pool = multiprocessing.Pool(args.parallel)
    pool.map(LatticeBscanSpi.make, args.device, chunksize=1)
