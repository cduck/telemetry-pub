/*
 * telemetry.cpp
 *
 *  Created on: Mar 2, 2015
 *      Author: Ducky
 *
 * Implementation for the base Telemetry class.
 */

#include <telemetry.h>

namespace telemetry {

size_t Telemetry::add_data(Data& new_data) {
  if (data_count >= MAX_DATA_PER_TELEMETRY) {
    do_error("MAX_DATA_PER_TELEMETRY limit reached.");
    return -1;
  }
  if (header_transmitted) {
    do_error("Cannot add new data after header transmitted.");
    return -1;
  }
  data[data_count] = &new_data;
  data_updated[data_count] = true;
  data_count++;
  return data_count - 1;
}

void Telemetry::mark_data_updated(size_t data_id) {
  data_updated[data_id] = true;
}

void Telemetry::transmit_header() {
  if (header_transmitted) {
    do_error("Cannot retransmit header.");
    return;
  }

  size_t packet_legnth = 2; // opcode + sequence
  for (int data_idx = 0; data_idx < data_count; data_idx++) {
    packet_legnth += 2; // data ID, data type
    packet_legnth += data[data_idx]->get_header_kvrs_length();
    packet_legnth += 1; // terminator record id
  }
  packet_legnth++;  // terminator "record"

  FixedLengthTransmitPacket packet(hal, packet_legnth);

  packet.write_uint8(OPCODE_HEADER);
  packet.write_uint8(packet_tx_sequence);
  for (int data_idx = 0; data_idx < data_count; data_idx++) {
    packet.write_uint8(data_idx+1);
    packet.write_uint8(data[data_idx]->get_data_type());
    data[data_idx]->write_header_kvrs(packet);
    packet.write_uint8(RECORDID_TERMINATOR);
  }
  packet.write_uint8(DATAID_TERMINATOR);

  packet.finish();

  packet_tx_sequence++;
  header_transmitted = true;
}

void Telemetry::do_io() {
  transmit_data();
  process_received_data();
}

void Telemetry::transmit_data() {
  if (!header_transmitted) {
    do_error("Must transmit header before transmitting data.");
    return;
  }

  // Keep a local copy to make it more thread-safe
  bool data_updated_local[MAX_DATA_PER_TELEMETRY];

  size_t packet_legnth = 2; // opcode + sequence
  for (int data_idx = 0; data_idx < data_count; data_idx++) {
    data_updated_local[data_idx] = data_updated[data_idx];
    data_updated[data_idx] = 0;
    if (data_updated_local[data_idx]) {
      packet_legnth += 1; // data ID
      packet_legnth += data[data_idx]->get_payload_length();
    }
  }
  packet_legnth++;  // terminator "record"

  FixedLengthTransmitPacket packet(hal, packet_legnth);

  packet.write_uint8(OPCODE_DATA);
  packet.write_uint8(packet_tx_sequence);
  for (int data_idx = 0; data_idx < data_count; data_idx++) {
    if (data_updated_local[data_idx]) {
      packet.write_uint8(data_idx+1);
      data[data_idx]->write_payload(packet);
    }
  }
  packet.write_uint8(DATAID_TERMINATOR);

  packet.finish();

  packet_tx_sequence++;
}

void Telemetry::process_received_data() {
  // TODO: implement me
}

size_t Telemetry::receive_available() {
  // TODO: implement me
  return 0;
}

uint8_t read_receive() {
  // TODO: implement me
  return 0;
}

FixedLengthTransmitPacket::FixedLengthTransmitPacket(HalInterface& hal,
    size_t length) :
        hal(hal),
        length(length),
        count(0) {
  hal.transmit_byte(SOF1);
  hal.transmit_byte(SOF2);

  hal.transmit_byte((length >> 8) & 0xff);
  hal.transmit_byte((length >> 0) & 0xff);

  valid = true;
}

void FixedLengthTransmitPacket::write_byte(uint8_t data) {
  if (!valid) {
    hal.do_error("Writing to invalid packet");
    return;
  } else if (count + 1 > length) {
    hal.do_error("Writing over packet length");
    return;
  }
  hal.transmit_byte(data);
  if (data == SOF1) {
    hal.transmit_byte(0x00);  // TODO: proper abstraction and magic numbers
  }
  count++;
}

void FixedLengthTransmitPacket::write_uint8(uint8_t data) {
  write_byte(data);
}

void FixedLengthTransmitPacket::write_uint16(uint16_t data) {
  write_byte((data >> 8) & 0xff);
  write_byte((data >> 0) & 0xff);
}

void FixedLengthTransmitPacket::write_uint32(uint32_t data) {
  write_byte((data >> 24) & 0xff);
  write_byte((data >> 16) & 0xff);
  write_byte((data >> 8) & 0xff);
  write_byte((data >> 0) & 0xff);
}

void FixedLengthTransmitPacket::write_float(float data) {
  // TODO: THIS IS ENDIANNESS DEPENDENT, ABSTRACT INTO HAL?
  uint8_t *float_array = (uint8_t*) &data;
  write_byte(float_array[0]);
  write_byte(float_array[1]);
  write_byte(float_array[2]);
  write_byte(float_array[3]);
}

void FixedLengthTransmitPacket::finish() {
  if (!valid) {
    hal.do_error("Finishing invalid packet");
  } else if (count != length) {
    hal.do_error("Packet under length");
  }

  // TODO: add CRC check here
}

}
