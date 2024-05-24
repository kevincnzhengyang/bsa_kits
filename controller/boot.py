#-*-coding:UTF-8-*-


'''
* @Author      : kevin.z.y <kevin.cn.zhengyang@gmail.com>
* @Date        : 2024-04-24 11:28:40
* @LastEditors : kevin.z.y <kevin.cn.zhengyang@gmail.com>
* @LastEditTime: 2024-05-03 20:36:43
* @FilePath    : /bsa_kits/controller/boot.py
* @Description : controller
* @Copyright (c) 2024 by Zheng, Yang, All Rights Reserved.
'''

import network
import aioespnow
import asyncio
from machine import Pin
from time import ticks_ms


class Peer(object):
    DEBOUNCE_TIME = 50
    HEARTBEAT_TIME = 1000
    LOSS_COUNT = 5

    def __init__(self, count: int, mac: bytes,
                 pin_n: int, pin_e: int, pin_b: int) -> object:
        self.mac = mac          # mac address in bytes
        # pin for button
        self.pin_button = Pin(pin_b, mode = Pin.IN, pull = Pin.PULL_DOWN)
        self.count = count+1    # counter for sequence
        self.seq = 0            # sequence for button release
        # dev for ESP NOW
        self.dev = None

        # pin for state led
        self.pin_normal = Pin(pin_n, mode = Pin.OUT)
        self.pin_error = Pin(pin_e, mode = Pin.OUT)
        self.enable = False     # ping result
        self.pin_normal.value(self.enable)      # not connected
        self.pin_error.value(not self.enable)

        self._reset_peer()

    def _reset_peer(self) -> None:
        self.rest_state = False
        self.previous_state = False
        self.current_state = False
        self.previous_debounced_state = False
        self.current_debounced_state = False
        self.last_check_tick = ticks_ms()

        self.loss = 0           # loss counter for ping
        self.last_hb_tick = self.last_check_tick
        self.last_state_tick = self.last_hb_tick

    def bind_dev(self, dev: aioespnow.AIOESPNow) -> None:
        self.dev = dev

    async def button_check(self, ms_now) -> None:
        # button check
        self.current_state = self.pin_button.value()
        state_changed = self.current_state != self.previous_state
        if state_changed:
            self.last_check_tick = ms_now
        state_stable = (ms_now - self.last_check_tick) > Peer.DEBOUNCE_TIME
        if state_stable and not state_changed:
            # stable but not changed
            self.last_check_tick = ms_now
            self.current_debounced_state = self.current_state
        self.previous_state = self.current_state
        if self.current_debounced_state != self.previous_debounced_state:
            if self.current_debounced_state == self.rest_state:
                # button released
                self.seq += 1
                if await self.dev.asend(self.mac, self.seq.to_bytes(1, 'big')):
                    print(f"[{self.mac}]->{self.seq}")
                else:
                    print(f"[{self.mac}]-/-{self.seq}")
                    self.seq -= 1   # reset sequence
                self.seq %= self.count      # rollover sequence
        self.previous_debounced_state = self.current_debounced_state

    async def hb_check(self, ms_now) -> None:
        # heartbeat check
        if not self.enable:
            self.pin_normal.value(self.enable)
            # print(f"[{self.mac}] ###")
            # already lost, flash LED
            if (ms_now - self.last_state_tick) > Peer.HEARTBEAT_TIME:
                # reverse LED
                self.pin_error.value(not self.pin_error.value())
                self.last_state_tick = ms_now   # reset
        elif (ms_now - self.last_hb_tick) > Peer.HEARTBEAT_TIME:
            self.loss += 1
            if self.loss > Peer.LOSS_COUNT:
                # lost hearbeat
                self.enable = False
                print(f"[{self.mac}] lost")

    async def update(self) -> None:
        ms_now = ticks_ms()     # get ticks

        # button check if enable
        if self.enable:
            await self.button_check(ms_now)

        # heart beat check
        await self.hb_check(ms_now)

    async def hb_handle(self, mac: bytes) -> None:
        if mac == self.mac:
            if not self.enable:
                # reset when peer heartbeat received
                self.enable = True
                self._reset_peer()
                self.pin_normal.value(self.enable)      # Turn on when connected
                self.pin_error.value(not self.enable)
                print(f"[{self.mac}] connected")
            else:
                self.last_hb_tick = ticks_ms()
                self.loss = 0
                # print(f"[{self.mac}] hearbeat")
        # else:
        #     print(f"[{self.mac}] is not [{mac}]")



class Controller(object):
    PERIOD = 0.01
    def __init__(self, peer_s: Peer, peer_r: Peer) -> object:
        self.peer_stage4 = peer_s   # peer for stage 4
        self.peer_rank6 = peer_r    # peer for rank 5
        self.dev = None             # device for ESP NOW

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
        self.dev.add_peer(self.peer_stage4.mac)
        self.dev.add_peer(self.peer_rank6.mac)
        self.peer_stage4.bind_dev(self.dev)
        self.peer_rank6.bind_dev(self.dev)

    async def recv_hb(self) -> None:
        print(f"heartbeat recv ...")
        async for mac, msg in self.dev:
            # print(f"from [{mac}: {msg}]")
            await self.peer_stage4.hb_handle(mac)
            await self.peer_rank6.hb_handle(mac)
        print("recv heartbeat finish")

    async def svc_loop(self) -> None:
        print(f"svc loop ...")
        try:
            while True:
                await self.peer_stage4.update()
                await self.peer_rank6.update()
                await asyncio.sleep(Controller.PERIOD)
            print("svc finish")
        except OSError as err:
            print(f"error: {err.args[1]}")


async def main() -> None:
    print(f"peer stage4 init")
    peer_stage4 = Peer(4, b"\x40\x22\xd8\xef\x09\x7c", 18, 19, 16)
    print(f"peer rank 4 init")
    peer_rank6 = Peer(6, b"\x40\x22\xd8\xea\x7d\xe4", 26, 27, 32)
    print(f"controller init")
    controller = Controller(peer_stage4, peer_rank6)
    print(f"preamble")
    controller.preamble()
    print(f"task recv hb")
    asyncio.create_task(controller.recv_hb())
    print(f"task svc loop")
    asyncio.create_task(controller.svc_loop())
    while True:
        await asyncio.sleep(120)
    print(f"main over")

asyncio.run(main())
