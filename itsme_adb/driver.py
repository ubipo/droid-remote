import asyncio
from enum import Enum
from functools import cached_property
import logging
from typing import Optional
from dataclasses import dataclass, field
from lxml import etree

from droid_remote.lxml_utils import attrib_or_error, element_to_string, elements_xpath
from droid_remote.device import adb


ITSME_PACKAGE_NAME = "be.bmid.itsme"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WrongScreenError(Exception):
  message: str
  screen: etree._Element
  parsers_tried: dict[str, "WrongScreenError"] = field(default_factory=dict)


def first(iterable):
  return next(iter(iterable), None)


def one_or_none(iterable):
  iterator = iter(iterable)
  first = next(iterator, None)
  try:
    next(iterator)
  except StopIteration:
    return first
  raise ValueError("More than one element")


async def launch():
  await adb.launch_app(ITSME_PACKAGE_NAME)


async def force_stop():
  await adb.force_stop_app(ITSME_PACKAGE_NAME)


@dataclass
class ActionBasicInfo():
  action: str
  app: str
  time: str


def parse_basic_info(container: etree._Element):
  card_texts = elements_xpath(container, ".//node[@text!='']")
  action, app, time = [attrib_or_error(text, "text") for text in card_texts]
  return ActionBasicInfo(action, app, time)


@dataclass
class NoPendingActionsHomeScreen():
  pass


@dataclass
class PendingActionsHomeScreen():
  action_count: int
  basic_info: ActionBasicInfo
  card_center: tuple[int, int]

  async def tap_card(self):
    return await adb.tap(self.card_center)


async def parse_home_screen(screen: Optional[etree._Element] = None):
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  no_pending_actions_node = one_or_none(elements_xpath(screen, "//node[@text='No pending actions']"))
  tap_the_card_text = one_or_none(elements_xpath(screen, "//node[@text='Tap the card to open']"))
  if no_pending_actions_node is None and tap_the_card_text is None:
    raise WrongScreenError("Neither 'No pending actions' nor 'Tap the card to open' found", screen)
  if no_pending_actions_node is not None and tap_the_card_text is not None:
    raise WrongScreenError("Both 'No pending actions' and 'Tap the card to open' found", screen)
  
  if no_pending_actions_node is not None:
    return NoPendingActionsHomeScreen()
  
  card = tap_the_card_text.getnext() # Next sibling
  direct_child_nodes = elements_xpath(card, "./node")
  if len(direct_child_nodes) == 2:
    basic_info_container, action_count_node = direct_child_nodes
    resource_id = action_count_node.attrib.get("resource-id")
    if resource_id != "action_count_tag":
      raise WrongScreenError(f"Expected second child of action card to be action_count_tag ({resource_id=})", screen)
    action_count = int(attrib_or_error(action_count_node, "text"))
  elif len(direct_child_nodes) == 1:
    basic_info_container = direct_child_nodes[0]
    action_count = 1
  else:
    raise WrongScreenError(f"Expected action card to have 1 or 2 children ({len(direct_child_nodes)=})", screen)
  basic_info = parse_basic_info(basic_info_container)
  card_center = adb.element_to_bounds(basic_info_container).center
  return PendingActionsHomeScreen(action_count, basic_info, card_center)


async def home_screen_tap_card():
  home_screen = await parse_home_screen()
  await home_screen.tap_card()


@dataclass
class ActionScreen():
  basic_info: ActionBasicInfo
  extra_info: list[str]
  """Often a more verbose description of the action, provided by the requester app"""
  details: list[str]
  """When confirming (instead of logging in): the thing being confirmed"""
  shared_data: list[str]
  confirm_button_center: tuple[int, int]
  reject_button_center: tuple[int, int]

  async def confirm(self):
    logger.debug(f"Confirming action for app {self.basic_info.app} ({self.confirm_button_center})")
    return await adb.tap(self.confirm_button_center)
  
  async def reject(self):
    logger.debug(f"Rejecting action for app {self.basic_info.app} ({self.reject_button_center})")
    return await adb.tap(self.reject_button_center)


SHARED_ID_DATA = "Shared ID data"


async def parse_action_screen(screen: Optional[etree._Element] = None):
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  
  shared_id_data = one_or_none(elements_xpath(screen, f"//node[@text='{SHARED_ID_DATA}']"))
  if shared_id_data is None:
    raise WrongScreenError(f"'{SHARED_ID_DATA}' not found", screen)
  
  shared_data_texts = shared_id_data.getparent().xpath(".//node[@text!='']")
  shared_data = [text.attrib["text"] for text in shared_data_texts]
  shared_data = [shared_data for shared_data in shared_data if shared_data != SHARED_ID_DATA]

  first_text = first(elements_xpath(screen, "//node[@text!='']"))
  basic_info_card = first_text.getparent()
  basic_info = parse_basic_info(basic_info_card)

  # Optionally provided by the requester app
  extra_info_e = one_or_none(elements_xpath(screen, "//node[@text='Info']"))
  if extra_info_e is not None:
    extra_info_text_es = extra_info_e.getnext().xpath(".//node[@text!='']")
    extra_info = [text.attrib["text"] for text in extra_info_text_es]
  else:
    extra_info = []

  details_e = one_or_none(elements_xpath(screen, "//node[@text='Details']"))
  if details_e is not None:
    details_text_es = details_e.getnext().xpath(".//node[@text!='']")
    details = [text.attrib["text"] for text in details_text_es]
  else:
    details = []

  confirm_button = one_or_none(elements_xpath(screen, "//node[node[@class='android.widget.Button']]/node[@text='Confirm']"))
  if confirm_button is None:
    raise WrongScreenError("'Confirm' button not found", screen)
  confirm_button_center = adb.element_to_bounds(confirm_button).center

  reject_button = one_or_none(elements_xpath(screen, "//node[node[@class='android.widget.Button']]/node[@text='Reject']"))
  if reject_button is None:
    raise WrongScreenError("'Reject' button not found", screen)
  reject_button_center = adb.element_to_bounds(reject_button).center

  logger.debug(f"Action screen: {basic_info}")

  return ActionScreen(basic_info, extra_info, details, shared_data, confirm_button_center, reject_button_center)


async def action_screen_confirm():
  action_screen = await parse_action_screen()
  await action_screen.confirm()


async def action_screen_reject():
  action_screen = await parse_action_screen()
  await action_screen.reject()


@dataclass
class PokaYokeImage():
  number: int
  center: tuple[int, int]

  async def tap(self):
    return await adb.tap(self.center)


@dataclass
class PokaYokeScreen():
  images: list[PokaYokeImage]

  def get_image(self, number: int):
    return next((image for image in self.images if image.number == number), None)
  
  async def tap_image(self, number: int):
    image = self.get_image(number)
    if image is None:
      raise ValueError(f"Image {number} not found")
    return await image.tap()


PINPAD_LAYOUT = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['<', '0', '>'],
]
# Size of the gaps as a ratio of the symbol width. Stays the same regardless of
# the device screen size.
PINPAD_GAP_RATIO = 0.5


@dataclass
class PinpadScreen():
  """The pinpad screen is not a grid of button views, but a single image view
  (as a security measure??). Because of this, we need to calculate the position
  of each symbol on the pinpad based on its size and the known pad layout."""

  pad_bounds: adb.Bounds

  @cached_property
  def symbol_size(self):
    nbro_y_gaps = len(PINPAD_LAYOUT) - 1
    return self.pad_bounds.height / (len(PINPAD_LAYOUT) + nbro_y_gaps * PINPAD_GAP_RATIO)
  
  @cached_property
  def gap_size(self):
    return self.symbol_size * PINPAD_GAP_RATIO

  def get_symbol_layout_coords(self, symbol: str):
    for row_i, row in enumerate(PINPAD_LAYOUT):
      for col_i, col in enumerate(row):
        if col == symbol:
          return (row_i, col_i)
    raise ValueError(f"Symbol {symbol} not found")

  def get_symbol_center(self, symbol: str):
    row_i, col_i = self.get_symbol_layout_coords(symbol)
    top_left_x = self.pad_bounds.x_min + col_i * (self.symbol_size + self.gap_size)
    top_left_y = self.pad_bounds.y_min + row_i * (self.symbol_size + self.gap_size)
    half_size = self.symbol_size // 2
    return (top_left_x + half_size, top_left_y + half_size)

  async def enter_pin(self, pin: str):
    symbols = pin + ">"
    for symbol in symbols:
      await self.tap_symbol(symbol)
      await asyncio.sleep(0.05)

  async def tap_symbol(self, symbol: str):
    symbol_center = self.get_symbol_center(symbol)
    return await adb.tap(symbol_center)


async def parse_post_confirm_screen(screen: Optional[etree._Element] = None):
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  poka_yoke_text = one_or_none(elements_xpath(screen, "//node[@text='Check and tap the icon to continue.']"))
  pin_entry_text = one_or_none(elements_xpath(screen, "//node[@text='Confirm with your itsme code']"))
  if poka_yoke_text is None and pin_entry_text is None:
    raise WrongScreenError("Neither 'Check and tap the icon to continue.' nor 'Confirm with your itsme code' found", screen)
  if poka_yoke_text is not None and pin_entry_text is not None:
    raise WrongScreenError("Both 'Check and tap the icon to continue.' and 'Confirm with your itsme code' found", screen)
  
  if poka_yoke_text is not None:
    # resource id like "image_23"
    image_nodes = elements_xpath(screen, "//node[starts-with(@resource-id, 'image_')]")
    images = [
      PokaYokeImage(
        int(attrib_or_error(image, "resource-id").removeprefix("image_")),
        adb.element_to_bounds(image).center
      )
      for image in image_nodes
    ]
    return PokaYokeScreen(images)
  
  pinpad_node = one_or_none(elements_xpath(screen, "//node[@resource-id='pinpad']"))
  if pinpad_node is None:
    raise WrongScreenError("pinpad not found", screen)
  # The image pinpad has a fixed aspect ratio of 3:4
  # It's bounds however may be larger than the actual pinpad depending on the 
  # device screen size
  pinpad_image_bounds = adb.element_to_bounds(pinpad_node)
  symbol_width = min(
    pinpad_image_bounds.width // 3,
    pinpad_image_bounds.height // 4
  )
  pinpad_width = symbol_width * 3
  pinpad_height = symbol_width * 4
  pinpad_center_x, pinpad_center_y = pinpad_image_bounds.center
  pinpad_bounds = adb.Bounds(
    pinpad_center_x - pinpad_width // 2,
    pinpad_center_y - pinpad_height // 2,
    pinpad_center_x + pinpad_width // 2,
    pinpad_center_y + pinpad_height // 2,
  )
  return PinpadScreen(pinpad_bounds)


async def poka_yoke_screen_tap_image(number: int):
  poka_yoke_screen = await parse_post_confirm_screen()
  await poka_yoke_screen.tap_image(number)


async def pinpad_screen_enter_pin(pin: str):
  pinpad_screen = await parse_post_confirm_screen()
  await pinpad_screen.enter_pin(pin)


@dataclass
class ActionExpiredScreen():
  ok_button_center: tuple[int, int]

  async def ok(self):
    return await adb.tap(self.ok_button_center)


async def parse_action_expired_screen(screen: Optional[etree._Element] = None):
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  action_expired_text = one_or_none(elements_xpath(screen, "//node[@text='Action has expired']"))
  ok_button = one_or_none(elements_xpath(screen, "//node[@text='OK']"))
  if action_expired_text is None or ok_button is None:
    raise WrongScreenError("'Action has expired' or 'OK' button not found", screen)
  
  return ActionExpiredScreen(adb.element_to_bounds(ok_button).center)


async def action_expired_screen_ok():
  action_expired_screen = await parse_action_expired_screen()
  await action_expired_screen.ok()


@dataclass
class PlayRatingScreen():
  not_now_button_center: tuple[int, int]
  
  async def not_now(self):
    return await adb.tap(self.not_now_button_center)


async def parse_play_rating_screen(screen: Optional[etree._Element] = None):
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  disclaimer_text = one_or_none(elements_xpath(screen, "//node[starts-with(@text, 'Reviews are public and include your account and device info.')]"))
  not_now_button = one_or_none(elements_xpath(screen, "//node[@text='Not now']"))
  if disclaimer_text is None or not_now_button is None:
    raise WrongScreenError("Disclaimer or 'Not now' button not found", screen)

  return PlayRatingScreen(adb.element_to_bounds(not_now_button).center)


async def play_rating_screen_not_now():
  play_rating_screen = await parse_play_rating_screen()
  await play_rating_screen.not_now()


@dataclass
class ActionConfirmedScreen():
  pass


async def parse_action_confirmed_screen(screen: Optional[etree._Element] = None):
  # The screen after confirming an action is a sole checkmark on a green background
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  texts = elements_xpath(screen, "//node[@text!='']")
  if len(texts) != 0:
    raise WrongScreenError("The action confirmed screen has no text", screen)
  nodes = elements_xpath(screen, "//node")
  surface_areas = [adb.element_to_bounds(node).surface_area for node in nodes]
  smallest_surface_area = min(surface_areas)
  activity_surface_area = max(surface_areas)
  if smallest_surface_area / activity_surface_area < 0.025:
    raise WrongScreenError("The action confirmed screen has no small elements", screen)
  return ActionConfirmedScreen()


Screen = NoPendingActionsHomeScreen | PendingActionsHomeScreen | ActionScreen | PokaYokeScreen | PinpadScreen | ActionExpiredScreen | PlayRatingScreen | ActionConfirmedScreen


async def parse_any_screen(screen: Optional[etree._Element] = None) -> Screen:
  if screen is None:
    screen = await adb.read_screen_hierarchy()
  parsers = [
    parse_home_screen, parse_action_screen, parse_post_confirm_screen,
    parse_action_expired_screen, parse_play_rating_screen,
    parse_action_confirmed_screen
  ]
  parsers_tried = {}
  for parser in parsers:
    try:
      return await parser(screen)
    except WrongScreenError as e:
      parsers_tried[parser.__name__] = e
      pass
  top_level_node = first(elements_xpath(screen, "/hierarchy/node"))
  top_level_package = top_level_node.attrib["package"]
  if top_level_package == ITSME_PACKAGE_NAME:
    raise WrongScreenError(f"Unknown screen (none of {[parser.__name__ for parser in parsers]} matched)", screen, parsers_tried)

  raise WrongScreenError(f"Unknown screen (no parsers matched). Top level package: {top_level_package} (expected {ITSME_PACKAGE_NAME})", screen)


class ConfirmStep(Enum):
  TAP_CARD = 1
  CONFIRM = 2
  POKA_YOKE = 3
  PIN = 4
  DONE = 5


@dataclass
class NoPendingActionsException(Exception):
  pass


@dataclass
class UnexpectedPendingActionException(Exception):
  wrong_basic_info: ActionBasicInfo
  expected_app_name: str


@dataclass
class ConfirmAppActionInteractionRequired(Exception):
  reason: str
  screen: Screen


async def confirm_app_action_step(
  pin: str,
  app_name: str,
  action: str,
  last_completed_step: ConfirmStep,
) -> ConfirmStep:
  screen = await parse_any_screen()
  if isinstance(screen, NoPendingActionsHomeScreen):
    logger.debug("No pending actions")
    if last_completed_step.value < ConfirmStep.PIN.value:
      raise NoPendingActionsException()
    return ConfirmStep.DONE
  elif isinstance(screen, PendingActionsHomeScreen):
    if screen.basic_info.app != app_name or screen.basic_info.action != action:
      raise UnexpectedPendingActionException(screen.basic_info, app_name)
    await screen.tap_card()
    return ConfirmStep.TAP_CARD
  elif isinstance(screen, ActionScreen):
    logger.debug(f"Confirming action for app {app_name}")
    await screen.confirm()
    return ConfirmStep.CONFIRM
  elif isinstance(screen, PokaYokeScreen):
    raise ConfirmAppActionInteractionRequired("Poka yoke", screen)
  elif isinstance(screen, PinpadScreen):
    await screen.enter_pin(pin)
    return ConfirmStep.PIN
  elif isinstance(screen, ActionExpiredScreen):
    raise Exception("Action expired")
  elif isinstance(screen, PlayRatingScreen):
    await screen.not_now()
    return last_completed_step
  elif isinstance(screen, ActionConfirmedScreen):
    return ConfirmStep.DONE

  raise Exception(f"Unknown screen type: {type(screen)}")


async def confirm_app_action(pin: str, app_name: str, action: str, max_tries: int = 3) -> str:
  for _ in range(max_tries):
    last_completed_step = ConfirmStep.TAP_CARD
    while True:
      last_completed_step = await confirm_app_action_step(pin, app_name, action, last_completed_step)
      if last_completed_step == ConfirmStep.DONE:
        return f"Confirmed app action {app_name}: {action}"
  
  raise Exception(f"Failed to confirm action after {max_tries} tries")
