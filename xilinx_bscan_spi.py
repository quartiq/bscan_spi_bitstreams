#!/usr/bin/python3
#
#  Copyright (C) 2015 Robert Jordens <jordens@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#

import migen as mg
import migen.build.generic_platform as mb
from migen.build import xilinx


"""
This migen script produces proxy bitstreams to allow programming SPI flashes
behind FPGAs.

Bitstream binaries built with this script are available at:
https://github.com/jordens/bscan_spi_bitstreams

JTAG signalling is connected directly to SPI signalling. CS_N is
asserted when the JTAG IR contains the USER1 instruction and the state is
SHIFT-DR and there has been one high bit on TDI.

https://github.com/m-labs/migen
"""


class JTAG2SPI(mg.Module):
    def __init__(self, spi=None):
        self.jtag = mg.Record([
            ("sel", 1),
            ("shift", 1),
            ("clk", 1),
            ("tdi", 1),
            ("tdo", 1),
        ])
        self.cs_n = mg.TSTriple()
        self.clk = mg.TSTriple()
        self.mosi = mg.TSTriple()
        self.miso = mg.TSTriple()

        # # #

        en = mg.Signal()
        self.cs_n.o.reset = mg.C(1)
        self.clock_domains.cd_rise = mg.ClockDomain(reset_less=True)
        self.clock_domains.cd_fall = mg.ClockDomain()
        if spi is not None:
            self.specials += [
                    self.cs_n.get_tristate(spi.cs_n),
                    self.mosi.get_tristate(spi.mosi),
                    self.miso.get_tristate(spi.miso),
            ]
            if hasattr(spi, "clk"):  # 7 Series drive it already
                self.specials += self.clk.get_tristate(spi.clk)
        self.comb += [
                en.eq(self.jtag.sel & self.jtag.shift),
                self.cd_fall.clk.eq(~self.jtag.clk),
                self.cd_fall.rst.eq(~en),
                self.cd_rise.clk.eq(self.jtag.clk),
                self.clk.oe.eq(en),
                self.cs_n.oe.eq(en),
                self.mosi.oe.eq(en),
                self.miso.oe.eq(0),
                self.clk.o.eq(self.jtag.clk),
                self.mosi.o.eq(self.jtag.tdi),
        ]
        # Some (Xilinx) bscan cells sample TDO on falling TCK and forward it.
        # MISO requires sampling on rising CLK and leads to one cycle of
        # latency.
        self.sync.rise += self.jtag.tdo.eq(self.miso.i)
        # If there are more than one tap on the JTAG chain, we need to drop
        # the inital bits. Select the flash with the first high bit and
        # deselect with ~en. This assumes that additional bits after a
        # transfer are ignored.
        self.sync.fall += mg.If(self.jtag.tdi, self.cs_n.o.eq(0))


class Spartan3(mg.Module):
    macro = "BSCAN_SPARTAN3"
    toolchain = "ise"

    def __init__(self, platform):
        platform.toolchain.bitgen_opt += " -g compress -g UnusedPin:Pullup"
        self.submodules.j2s = j2s = JTAG2SPI(platform.request("spiflash"))
        self.specials += [
                mg.Instance(
                    self.macro,
                    o_SHIFT=j2s.jtag.shift, o_SEL1=j2s.jtag.sel,
                    o_DRCK1=j2s.jtag.clk,
                    o_TDI=j2s.jtag.tdi, i_TDO1=j2s.jtag.tdo,
                    i_TDO2=0),
        ]


class Spartan3A(Spartan3):
    macro = "BSCAN_SPARTAN3A"


class Spartan6(mg.Module):
    toolchain = "ise"

    def __init__(self, platform):
        platform.toolchain.bitgen_opt += " -g compress -g UnusedPin:Pullup"
        self.submodules.j2s = j2s = JTAG2SPI(platform.request("spiflash"))
        self.specials += [
                mg.Instance(
                    "BSCAN_SPARTAN6", p_JTAG_CHAIN=1,
                    o_SHIFT=j2s.jtag.shift, o_SEL=j2s.jtag.sel,
                    o_TCK=j2s.jtag.clk,
                    o_TDI=j2s.jtag.tdi, i_TDO=j2s.jtag.tdo),
        ]




class Series7(mg.Module):
    toolchain = "vivado"

    def __init__(self, platform):
        platform.toolchain.bitstream_commands.extend([
            "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            "set_property BITSTREAM.CONFIG.UNUSEDPIN Pullnone [current_design]"
        ])
        self.submodules.j2s = j2s = JTAG2SPI(platform.request("spiflash"))
        self.specials += [
                mg.Instance(
                    "BSCANE2", p_JTAG_CHAIN=1,
                    o_SHIFT=j2s.jtag.shift, o_SEL=j2s.jtag.sel,
                    o_TCK=j2s.jtag.clk,
                    o_TDI=j2s.jtag.tdi, i_TDO=j2s.jtag.tdo),
                mg.Instance(
                    "STARTUPE2", i_CLK=0, i_GSR=0, i_GTS=0,
                    i_KEYCLEARB=0, i_PACK=1, i_USRCCLKO=j2s.jtag.clk,
                    i_USRCCLKTS=0, i_USRDONEO=1, i_USRDONETS=1)
        ]


class Ultrascale(mg.Module):
    toolchain = "vivado"

    def __init__(self, platform):
        platform.toolchain.bitstream_commands.extend([
            "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            "set_property BITSTREAM.CONFIG.UNUSEDPIN Pullnone [current_design]",
        ])
        self.submodules.j2s0 = j2s0 = JTAG2SPI()
        self.submodules.j2s1 = j2s1 = JTAG2SPI(platform.request("spiflash"))
        self.specials += [
                mg.Instance("BSCANE2", p_JTAG_CHAIN=1,
                    o_SHIFT=j2s0.jtag.shift, o_SEL=j2s0.jtag.sel,
                    o_TCK=j2s0.jtag.clk,
                    o_TDI=j2s0.jtag.tdi, i_TDO=j2s0.jtag.tdo),
                mg.Instance("BSCANE2", p_JTAG_CHAIN=2,
                    o_SHIFT=j2s1.jtag.shift, o_SEL=j2s1.jtag.sel,
                    o_TCK=j2s1.jtag.clk,
                    o_TDI=j2s1.jtag.tdi, i_TDO=j2s1.jtag.tdo),
                mg.Instance("STARTUPE3", i_GSR=0, i_GTS=0,
                    i_KEYCLEARB=0, i_PACK=1,
                    i_USRDONEO=1, i_USRDONETS=1,
                    i_USRCCLKO=j2s0.clk.o, i_USRCCLKTS=~j2s0.clk.oe,
                    i_FCSBO=j2s0.cs_n.o, i_FCSBTS=~j2s0.cs_n.oe,
                    o_DI=mg.Cat(0, j2s0.miso.i, 0, 0),
                    i_DO=mg.Cat(j2s0.mosi.o, 0, 0, 0),
                    i_DTS=mg.Cat(~j2s0.mosi.oe, ~j2s0.miso.oe, 1, 1))
        ]


class XilinxBscanSpi(xilinx.XilinxPlatform):
    packages = {
        # (package-speedgrade, id): [cs_n, clk, mosi, miso, *pullups]
        ("cp132", 1): ["M2", "N12", "N2", "N8"],
        ("fg320", 1): ["U3", "U16", "T4", "N10"],
        ("fg320", 2): ["V3", "U16", "T11", "V16"],
        ("fg484", 1): ["Y4", "AA20", "AB14", "AB20"],
        ("fgg484", 1): ["Y4", "AA20", "AB14", "AB20"],
        ("fgg400", 1): ["Y2", "Y19", "W12", "W18"],
        ("ftg256", 1): ["T2", "R14", "P10", "T14"],
        ("ft256", 1): ["T2", "R14", "P10", "T14"],
        ("fg400", 1): ["Y2", "Y19", "W12", "W18"],
        ("cs484", 1): ["U7", "V17", "V13", "W17"],
        ("qg144-2", 1): ["P38", "P70", "P64", "P65", "P62", "P61"],
        ("cpg196-2", 1): ["P2", "N13", "P11", "N11", "N10", "P10"],
        ("cpg236-1", 1): ["K19", None, "D18", "D19", "G18", "F18"],
        ("csg484-2", 1): ["AB5", "W17", "AB17", "Y17", "V13", "W13"],
        ("csg324-2", 1): ["V3", "R15", "T13", "R13", "T14", "V14"],
        ("csg324-1", 1): ["L13", None, "K17", "K18", "L14", "M14"],
        ("fbg484-1", 1): ["T19", None, "P22", "R22", "P21", "R21"],
        ("fbg484-1", 2): ["L16", None, "H18", "H19", "G18", "F19"],
        ("fbg676-1", 1): ["C23", None, "B24", "A25", "B22", "A22"],
        ("ffg901-1", 1): ["V26", None, "R30", "T30", "R28", "T28"],
        ("ffg1156-1", 1): ["V30", None, "AA33", "AA34", "Y33", "Y34"],
        ("ffg1157-1", 1): ["AL33", None, "AN33", "AN34", "AK34", "AL34"],
        ("ffg1158-1", 1): ["C24", None, "A23", "A24", "B26", "A26"],
        ("ffg1926-1", 1): ["AK33", None, "AN34", "AN35", "AJ34", "AK34"],
        ("fhg1761-1", 1): ["AL36", None, "AM36", "AN36", "AJ36", "AJ37"],
        ("flg1155-1", 1): ["AL28", None, "AE28", "AF28", "AJ29", "AJ30"],
        ("flg1932-1", 1): ["V32", None, "T33", "R33", "U31", "T31"],
        ("flg1926-1", 1): ["AK33", None, "AN34", "AN35", "AJ34", "AK34"],

        ("ffva1156-2-e", 1): ["G26", None, "M20", "L20", "R21", "R22"],
        ("ffva1156-2-e", "sayma"): ["K21", None, "M20", "L20", "R21", "R22"],
    }

    pinouts = {
        # bitstreams are named by die, package does not matter, speed grade
        # should not matter.
        #
        # chip: (package, id, standard, class)
        "xc3s100e": ("cp132", 1, "LVCMOS33", Spartan3),
        "xc3s1200e": ("fg320", 1, "LVCMOS33", Spartan3),
        "xc3s1400a": ("fg484", 1, "LVCMOS33", Spartan3A),
        "xc3s1400an": ("fgg484", 1, "LVCMOS33", Spartan3A),
        "xc3s1600e": ("fg320", 1, "LVCMOS33", Spartan3),
        "xc3s200a": ("fg320", 2, "LVCMOS33", Spartan3A),
        "xc3s200an": ("ftg256", 1, "LVCMOS33", Spartan3A),
        "xc3s250e": ("cp132", 1, "LVCMOS33", Spartan3),
        "xc3s400a": ("fg320", 2, "LVCMOS33", Spartan3A),
        "xc3s400an": ("fgg400", 1, "LVCMOS33", Spartan3A),
        "xc3s500e": ("cp132", 1, "LVCMOS33", Spartan3),
        "xc3s50a": ("ft256", 1, "LVCMOS33", Spartan3A),
        "xc3s50an": ("ftg256", 1, "LVCMOS33", Spartan3A),
        "xc3s700a": ("fg400", 1, "LVCMOS33", Spartan3A),
        "xc3s700an": ("fgg484", 1, "LVCMOS33", Spartan3A),
        "xc3sd1800a": ("cs484", 1, "LVCMOS33", Spartan3A),
        "xc3sd3400a": ("cs484", 1, "LVCMOS33", Spartan3A),

        "xc6slx100": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx100t": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx150": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx150t": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx16": ("cpg196-2", 1, "LVCMOS33", Spartan6),
        "xc6slx25": ("csg324-2", 1, "LVCMOS33", Spartan6),
        "xc6slx25t": ("csg324-2", 1, "LVCMOS33", Spartan6),
        "xc6slx45": ("csg324-2", 1, "LVCMOS33", Spartan6),
        "xc6slx45t": ("csg324-2", 1, "LVCMOS33", Spartan6),
        "xc6slx4": ("cpg196-2", 1, "LVCMOS33", Spartan6),
        "xc6slx4t": ("qg144-2", 1, "LVCMOS33", Spartan6),
        "xc6slx75": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx75t": ("csg484-2", 1, "LVCMOS33", Spartan6),
        "xc6slx9": ("cpg196-2", 1, "LVCMOS33", Spartan6),
        "xc6slx9t": ("qg144-2", 1, "LVCMOS33", Spartan6),

        "xc7a100t": ("csg324-1", 1, "LVCMOS25", Series7),
        "xc7a15t": ("cpg236-1", 1, "LVCMOS25", Series7),
        "xc7a200t": ("fbg484-1", 1, "LVCMOS25", Series7),
        "xc7a35t": ("cpg236-1", 1, "LVCMOS25", Series7),
        "xc7a50t": ("cpg236-1", 1, "LVCMOS25", Series7),
        "xc7a75t": ("csg324-1", 1, "LVCMOS25", Series7),
        "xc7k160t": ("fbg484-1", 2, "LVCMOS25", Series7),
        "xc7k325t": ("fbg676-1", 1, "LVCMOS25", Series7),
        "xc7k355t": ("ffg901-1", 1, "LVCMOS25", Series7),
        "xc7k410t": ("fbg676-1", 1, "LVCMOS25", Series7),
        "xc7k420t": ("ffg1156-1", 1, "LVCMOS25", Series7),
        "xc7k480t": ("ffg1156-1", 1, "LVCMOS25", Series7),
        "xc7k70t": ("fbg484-1", 2, "LVCMOS25", Series7),
        "xc7v2000t": ("fhg1761-1", 1, "LVCMOS18", Series7),
        "xc7v585t": ("ffg1157-1", 1, "LVCMOS18", Series7),
        "xc7vh580t": ("flg1155-1", 1, "LVCMOS18", Series7),
        "xc7vh870t": ("flg1932-1", 1, "LVCMOS18", Series7),
        "xc7vx1140t": ("flg1926-1", 1, "LVCMOS18", Series7),
        "xc7vx330t": ("ffg1157-1", 1, "LVCMOS18", Series7),
        "xc7vx415t": ("ffg1157-1", 1, "LVCMOS18", Series7),
        "xc7vx485t": ("ffg1157-1", 1, "LVCMOS18", Series7),
        "xc7vx550t": ("ffg1158-1", 1, "LVCMOS18", Series7),
        "xc7vx690t": ("ffg1157-1", 1, "LVCMOS18", Series7),
        "xc7vx980t": ("ffg1926-1", 1, "LVCMOS18", Series7),

        "xcku040": ("ffva1156-2-e", 1, "LVCMOS18", Ultrascale),
        # "xcku040": ("ffva1156-2-e", "sayma", "LVCMOS18", Ultrascale),
    }

    def __init__(self, device, pins, std, toolchain="ise"):
        ios = [self.make_spi(0, pins, std, toolchain)]
        xilinx.XilinxPlatform.__init__(self, device, ios, toolchain=toolchain)

    @staticmethod
    def make_spi(i, pins, std, toolchain):
        pu = "PULLUP" if toolchain == "ise" else "PULLUP TRUE"
        cs_n, clk, mosi, miso = pins[:4]
        io = ["spiflash", i,
            mb.Subsignal("cs_n", mb.Pins(cs_n)),
            mb.Subsignal("mosi", mb.Pins(mosi)),
            mb.Subsignal("miso", mb.Pins(miso), mb.Misc(pu)),
            mb.IOStandard(std),
            ]
        if clk:
            io.append(mb.Subsignal("clk", mb.Pins(clk)))
        for i, p in enumerate(pins[4:]):
            io.append(mb.Subsignal("pullup{}".format(i), mb.Pins(p),
                                mb.Misc(pu)))
        return io

    @classmethod
    def make(cls, device, errors=False):
        pkg, id, std, Top = cls.pinouts[device]
        pins = cls.packages[(pkg, id)]
        platform = cls("{}-{}".format(device, pkg), pins, std, Top.toolchain)
        top = Top(platform)
        name = "bscan_spi_{}".format(device)
        dir = "build_{}".format(device)
        try:
            platform.build(top, build_name=name, build_dir=dir)
        except Exception as e:
            print(("ERROR: xilinx_bscan_spi build failed "
                  "for {}: {}").format(device, e))
            if errors:
                raise


if __name__ == "__main__":
    import argparse
    import multiprocessing
    p = argparse.ArgumentParser(description="build bscan_spi bitstreams "
                                "for openocd jtagspi flash driver")
    p.add_argument("device", nargs="*",
                   default=sorted(list(XilinxBscanSpi.pinouts)),
                   help="build for these devices (default: %(default)s)")
    p.add_argument("-p", "--parallel", default=1, type=int,
                   help="number of parallel builds (default: %(default)s)")
    args = p.parse_args()
    pool = multiprocessing.Pool(args.parallel)
    pool.map(XilinxBscanSpi.make, args.device, chunksize=1)
