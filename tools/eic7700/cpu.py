# SPDX-License-Identifier: MIT
"""Select EIC7700 boot clock settings from the board device tree."""
from collections import deque
import subprocess


def get(dtb, node, prop, kind='u', default=None):
    options = [] if default is None else ['-d', default]
    return subprocess.check_output(
        ['fdtget', *options, '-t', kind, str(dtb), node, prop], text=True).split()


def children(dtb, node):
    names = subprocess.check_output(['fdtget', '-l', str(dtb), node], text=True)
    return [node.rstrip('/') + '/' + name for name in names.split()]


def enabled(dtb, node):
    return get(dtb, node, 'status', 's', default='okay') in (['okay'], ['ok'])


def phandle_path(dtb, handle):
    pending = deque(['/'])
    while pending:
        node = pending.popleft()
        if get(dtb, node, 'phandle', default='') == [handle]:
            return node
        pending.extend(children(dtb, node))
    raise ValueError(f'device tree phandle {handle} not found')


def boot_cpu_rate(dtb):
    handle, = get(dtb, '/cpus/cpu@0', 'operating-points-v2')
    table = phandle_path(dtb, handle)

    if not enabled(dtb, table) or 'operating-points-v2' not in get(dtb, table, 'compatible', 's'):
        raise ValueError('boot CPU operating point table is disabled or incompatible')

    rates = []
    for node in children(dtb, table):
        props = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).split()
        if 'opp-hz' not in props or not enabled(dtb, node):
            continue
        if 'turbo-mode' in props or 'opp-supported-hw' in props:
            continue
        high, low = map(int, get(dtb, node, 'opp-hz'))
        rates.append((high << 32) | low)
    if not rates:
        raise ValueError('no enabled normal CPU operating point')
    return max(rates)


def p550_gpio_rate(dtb, rate=None):
    """Return the rate to apply after DDR training on a GPIO-selected P550."""
    cpu = '/cpus/cpu@0'
    if 'sifive,hifive-premier-p550' not in get(dtb, '/', 'compatible', 's'):
        return 0
    if rate is None:
        # A DDR-only input may describe memory wiring without a CPU OPP table.
        if not get(dtb, cpu, 'operating-points-v2', default=''):
            return 0
        rate = boot_cpu_rate(dtb)
    if rate <= 1400000000:
        return 0
    supply = get(dtb, cpu, 'cpu-supply', default='')
    if not supply:
        raise ValueError('P550 high boot frequency requires a CPU supply')
    rail = phandle_path(dtb, supply[0])
    if not enabled(dtb, rail):
        raise ValueError('P550 CPU supply is disabled')
    compatible = get(dtb, rail, 'compatible', 's')
    minimum, = map(int, get(dtb, rail, 'regulator-min-microvolt'))
    maximum, = map(int, get(dtb, rail, 'regulator-max-microvolt'))
    if not minimum <= 900000 <= maximum:
        raise ValueError('P550 high boot frequency requires a 0.9 V supply')
    if 'regulator-fixed' in compatible:
        if minimum == maximum:
            return 0
        raise ValueError('expected a fixed voltage for the P550 CPU supply')
    if 'regulator-gpio' in compatible:
        gpio = get(dtb, rail, 'gpios')
        states = list(map(int, get(dtb, rail, 'states')))
        if len(gpio) == 3 and gpio[1:] == ['30', '0']:
            port = phandle_path(dtb, gpio[0])
            controller = port.rsplit('/', 1)[0]
            if (enabled(dtb, port) and enabled(dtb, controller) and
                    get(dtb, port, 'reg') == ['2'] and
                    get(dtb, controller, 'reg')[:2] == ['0', str(0x51600000)] and
                    (900000, 1) in zip(states[::2], states[1::2]) and
                    get(dtb, rail, 'gpios-states') == ['1']):
                return rate
    raise ValueError('unsupported P550 CPU voltage selector')
