#-*-coding:UTF-8-*-


'''
* @Author      : kevin.z.y <kevin.cn.zhengyang@gmail.com>
* @Date        : 2024-04-24 11:28:40
* @LastEditors : kevin.z.y <kevin.cn.zhengyang@gmail.com>
* @LastEditTime: 2024-04-25 23:19:26
* @FilePath    : /hello_world/home/kevin/esp/micropython/bsa_kits/stage4/boot.py
* @Description : stage 4
* @Copyright (c) 2024 by Zheng, Yang, All Rights Reserved.
'''

import network
import aioespnow
import asyncio
from machine import Pin
from time import ticks_ms


class Stage4(object):
    LIGHT_COUNT = 4

    def __init__(self, pin_1: int, pin_2: int, pin_3: int, pin_4: int) -> object:
        # pin for lights
        self.pins = [Pin(pin_1, mode = Pin.OUT), Pin(pin_2, mode = Pin.OUT),
                     Pin(pin_3, mode = Pin.OUT), Pin(pin_4, mode = Pin.OUT)]

    def handle_cmd(self, seq: int) -> None:
        if Stage4.LIGHT_COUNT < seq:
            for pin in self.pins:
                pin.value(False)
        else:
            for i in range(seq):
                self.pins[i].value(True)


class Node(object):
    HEARTBEAT_PERIOD = 0.5

    def __init__(self, host_mac: bytes, light: object) -> object:
        self.host_mac = host_mac
        self.dev = None             # device for ESP NOW
        self.seq = 0                # sequence
        self.light = light

    def preamble(self) -> None:
        # prepare ESP-NOW
        # Enable station mode for ESP
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()

        # Returns AIOESPNow enhanced with async support
        self.dev = aioespnow.AIOESPNow()
        self.dev.active(True)

        # add peers
        self.dev.add_peer(self.host_mac)

        # turn off lights
        self.light.handle_cmd(Stage4.LIGHT_COUNT+1)

    # Send a periodic ping to a peer
    async def heartbeat(self):
        print(f"heartbeat ...")
        while True:
            if not await self.dev.asend(self.host_mac, self.seq.to_bytes(1, 'big')):
                print("Heartbeat Lost")
            await asyncio.sleep(Node.HEARTBEAT_PERIOD)

    async def recv_cmd(self) -> None:
        print(f"cmd recv ...")
        async for mac, msg in self.dev:
            print(f"from [{mac}: {msg}]")
            self.seq = int.from_bytes(msg, 'big')
            self.light.handle_cmd(self.seq)
        print("recv heartbeat finish")


async def main() -> None:
    print(f"stage4 init")
    stage4 = Stage4(18, 19, 22, 23)
    print(f"node init")
    node = Node(b'\x40\x22\xd8\xea\x9f\x88', stage4)
    print(f"preamble")
    node.preamble()
    print(f"task send hb")
    asyncio.create_task(node.heartbeat())
    print(f"task recv cmd")
    asyncio.create_task(node.recv_cmd())
    while True:
        await asyncio.sleep(120)
    print(f"main over")

asyncio.run(main())
